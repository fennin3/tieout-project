import pytest

from recon.engine.runner import run_reconciliation
from recon.models import Break, LedgerEntry, Match, ReconRun
from tests.builders import (
    BUSINESS_DAY,
    create_account,
    create_ledger_entry,
    create_statement,
    create_statement_line,
)


@pytest.mark.django_db
def test_run_reconciliation_auto_match_sets_entry_match_and_flag() -> None:
    account = create_account()
    statement_line = create_statement_line(create_statement(account), row_index=1)
    ledger_entry = create_ledger_entry(account, "JE-001")

    run = run_reconciliation(account, BUSINESS_DAY)

    ledger_entry.refresh_from_db()
    assert run.state == ReconRun.State.SUCCEEDED
    assert run.auto_count == 1
    assert ledger_entry.match is not None
    assert ledger_entry.match.state == Match.State.AUTO
    assert list(ledger_entry.match.statement_lines.all()) == [statement_line]
    assert ledger_entry.is_matched is True
    assert ledger_entry.matched_at is not None


@pytest.mark.django_db
def test_run_reconciliation_creates_open_breaks_for_unmatched_items() -> None:
    account = create_account()
    statement_line = create_statement_line(
        create_statement(account), row_index=1, cd="D", amount="75.00", ref_ours="NONREF"
    )
    ledger_entry = create_ledger_entry(account, "JE-001", cd="C", amount="950.00", ref="CHQ-1")

    run = run_reconciliation(account, BUSINESS_DAY)

    assert run.break_count == 2
    assert set(Break.objects.values_list("side", "statement_line", "ledger_entry", "state")) == {
        (Break.Side.STATEMENT, statement_line.id, None, Break.State.OPEN),
        (Break.Side.LEDGER, None, ledger_entry.id, Break.State.OPEN),
    }


@pytest.mark.django_db
def test_run_reconciliation_rerun_creates_no_new_matches() -> None:
    account = create_account()
    statement = create_statement(account)
    create_statement_line(statement, row_index=1)
    create_statement_line(statement, row_index=2, amount="9985.00", ref_ours="INV2002")
    create_ledger_entry(account, "JE-001")
    create_ledger_entry(account, "JE-002", amount="10000.00", ref="INV2002")
    first_run = run_reconciliation(account, BUSINESS_DAY)

    second_run = run_reconciliation(account, BUSINESS_DAY)

    assert (first_run.auto_count, first_run.review_count) == (1, 1)
    assert (second_run.auto_count, second_run.review_count) == (0, 0)
    assert Match.objects.count() == 2
    assert LedgerEntry.objects.filter(match__isnull=False).count() == 2
