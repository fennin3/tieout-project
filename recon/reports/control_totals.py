"""Control-total checks for statement balances and reconciliation coverage."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Case, DecimalField, F, QuerySet, Sum, When

from recon.models import Account, Break, LedgerEntry, Match, Statement, StatementLine

ZERO = Decimal("0.00")
CLEARED_STATES = (Match.State.AUTO, Match.State.APPROVED)
SIGNED_AMOUNT = Case(
    When(cd="D", then=-F("amount")),
    default=F("amount"),
    output_field=DecimalField(max_digits=18, decimal_places=2),
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    expected: Decimal
    actual: Decimal

    @property
    def difference(self) -> Decimal:
        return self.actual - self.expected

    @property
    def status(self) -> str:
        return "PASS" if self.difference == 0 else "FAIL"


@dataclass(frozen=True)
class ControlTotalsReport:
    account_code: str
    as_of_date: date
    statement_ref: str
    checks: tuple[CheckResult, ...]


def build_control_totals(account: Account, as_of_date: date) -> ControlTotalsReport:
    """Compute statement balance, coverage and ledger flag checks up to as_of_date."""
    statement = Statement.objects.filter(account=account, closing_date__lte=as_of_date).latest(
        "closing_date"
    )
    statement_lines = StatementLine.objects.filter(
        statement__account=account, value_date__lte=as_of_date
    )
    ledger_entries = LedgerEntry.objects.filter(account=account, value_date__lte=as_of_date)

    return ControlTotalsReport(
        account_code=account.code,
        as_of_date=as_of_date,
        statement_ref=statement.statement_ref,
        checks=(
            _statement_balance_check(statement),
            _statement_coverage_check(statement_lines),
            _ledger_coverage_check(ledger_entries),
            CheckResult(
                name="ledger_flags",
                expected=_signed_total(ledger_entries.filter(match__state__in=CLEARED_STATES)),
                actual=_signed_total(ledger_entries.filter(is_matched=True)),
            ),
        ),
    )


def _signed(cd: str, amount: Decimal) -> Decimal:
    return -amount if cd == "D" else amount


def _signed_total(queryset: QuerySet) -> Decimal:
    return queryset.aggregate(total=Sum(SIGNED_AMOUNT))["total"] or ZERO


def _statement_balance_check(statement: Statement) -> CheckResult:
    statement_lines = statement.lines.all()
    credits = statement_lines.filter(cd="C").aggregate(total=Sum("amount"))["total"] or ZERO
    debits = statement_lines.filter(cd="D").aggregate(total=Sum("amount"))["total"] or ZERO
    opening_signed = _signed(statement.opening_cd, statement.opening_amount)
    return CheckResult(
        name="statement_balance",
        expected=_signed(statement.closing_cd, statement.closing_amount),
        actual=opening_signed + credits - debits,
    )


def _statement_coverage_check(statement_lines: QuerySet) -> CheckResult:
    cleared = statement_lines.filter(
        id__in=StatementLine.objects.filter(matches__state__in=CLEARED_STATES).values("id")
    )
    pending = statement_lines.filter(
        id__in=StatementLine.objects.filter(matches__state=Match.State.PENDING_REVIEW).values("id")
    )
    open_break = statement_lines.filter(
        id__in=Break.objects.filter(side=Break.Side.STATEMENT, state=Break.State.OPEN).values(
            "statement_line_id"
        )
    )
    return CheckResult(
        name="statement_coverage",
        expected=_signed_total(statement_lines),
        actual=_signed_total(cleared) + _signed_total(pending) + _signed_total(open_break),
    )


def _ledger_coverage_check(ledger_entries: QuerySet) -> CheckResult:
    cleared = ledger_entries.filter(match__state__in=CLEARED_STATES)
    pending = ledger_entries.filter(match__state=Match.State.PENDING_REVIEW)
    open_break = ledger_entries.filter(
        id__in=Break.objects.filter(side=Break.Side.LEDGER, state=Break.State.OPEN).values(
            "ledger_entry_id"
        )
    )
    return CheckResult(
        name="ledger_coverage",
        expected=_signed_total(ledger_entries),
        actual=_signed_total(cleared) + _signed_total(pending) + _signed_total(open_break),
    )
