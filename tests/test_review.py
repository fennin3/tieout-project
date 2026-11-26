import pytest

from recon.exceptions import ReviewError
from recon.models import Match
from recon.services.review import review_match
from tests.builders import (
    create_account,
    create_ledger_entry,
    create_match,
    create_statement,
    create_statement_line,
)


@pytest.mark.django_db
def test_review_match_approve_sets_approved_and_reviewer() -> None:
    account = create_account()
    match = create_match(
        create_statement_line(create_statement(account), row_index=1, amount="9985.00"),
        create_ledger_entry(account, "JE-001", amount="10000.00"),
        state=Match.State.PENDING_REVIEW,
    )

    review_match(str(match.id), "approve", "a.osei", "Bank deducted a 15.00 wire fee")

    match.refresh_from_db()
    assert match.state == Match.State.APPROVED
    assert match.reviewed_by == "a.osei"
    assert match.reviewed_at is not None


@pytest.mark.django_db
def test_review_match_rejects_auto_match() -> None:
    account = create_account()
    match = create_match(
        create_statement_line(create_statement(account), row_index=1),
        create_ledger_entry(account, "JE-001"),
        state=Match.State.AUTO,
    )

    with pytest.raises(ReviewError, match="only pending_review"):
        review_match(str(match.id), "approve", "a.osei", "")
