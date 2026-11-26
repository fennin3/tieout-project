import pytest

from recon.engine.runner import run_reconciliation
from recon.reports.control_totals import build_control_totals
from tests.builders import (
    BUSINESS_DAY,
    create_account,
    create_ledger_entry,
    create_statement,
    create_statement_line,
)


@pytest.mark.django_db
def test_build_control_totals_passes_for_balanced_auto_matched_statement() -> None:
    account = create_account()
    statement = create_statement(account, opening_amount="1000.00", closing_amount="1350.00")
    create_statement_line(statement, row_index=1, cd="C", amount="500.00", ref_ours="INV1001")
    create_statement_line(statement, row_index=2, cd="D", amount="150.00", ref_ours="PAY-2001")
    create_ledger_entry(account, "JE-001", cd="D", amount="500.00", ref="INV1001")
    create_ledger_entry(account, "JE-002", cd="C", amount="150.00", ref="PAY-2001")
    run_reconciliation(account, BUSINESS_DAY)

    report = build_control_totals(account, BUSINESS_DAY)

    assert [check.name for check in report.checks] == [
        "statement_balance",
        "statement_coverage",
        "ledger_coverage",
        "ledger_flags",
    ]
    assert all(check.status == "PASS" for check in report.checks)
