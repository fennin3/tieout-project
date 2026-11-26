"""Small builders for engine inputs, input files and database rows used in tests."""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from recon.engine.rules import EntryIn, LineIn
from recon.models import Account, LedgerEntry, Match, Statement, StatementLine

BUSINESS_DAY = date(2026, 11, 2)
LEDGER_HEADER = "entry_ref,value_date,cd,amount,ref,narrative"


def make_line(
    line_id: int = 1,
    cd: str = "C",
    amount: str = "100.00",
    refs: tuple[str, ...] = ("INV1001", "NGB0001"),
    value_date: date = BUSINESS_DAY,
    book_date: date | None = None,
    narrative: str = "",
) -> LineIn:
    """Build a statement line input for the matching engine."""
    return LineIn(
        id=line_id,
        value_date=value_date,
        book_date=book_date,
        cd=cd,
        amount=Decimal(amount),
        refs=refs,
        narrative=narrative,
    )


def make_entry(
    entry_id: int = 1,
    cd: str = "D",
    amount: str = "100.00",
    ref: str = "INV1001",
    value_date: date = BUSINESS_DAY,
    narrative: str = "",
) -> EntryIn:
    """Build a ledger entry input for the matching engine."""
    return EntryIn(
        id=entry_id,
        value_date=value_date,
        cd=cd,
        amount=Decimal(amount),
        ref=ref,
        narrative=narrative,
    )


def mt940_text(
    transaction_lines: Sequence[str],
    opening: str = "C261030USD1000,00",
    closing: str = "C261102USD1000,00",
) -> str:
    """Wrap :61:/:86: lines in the header and balance fields of an MT940 statement."""
    return "\n".join(
        [
            ":20:NGB261102001",
            ":25:0048192031",
            ":28C:00305/001",
            f":60F:{opening}",
            *transaction_lines,
            f":62F:{closing}",
        ]
    )


def ledger_csv_text(rows: Sequence[str]) -> str:
    """Build ledger CSV content with the required header row."""
    return "\n".join([LEDGER_HEADER, *rows]) + "\n"


def create_account(code: str = "NGB-USD-01") -> Account:
    """Create a USD account."""
    return Account.objects.create(code=code, name="Northgate Bank USD nostro", currency="USD")


def create_statement(
    account: Account,
    opening_amount: str = "1000.00",
    closing_amount: str = "1000.00",
    opening_cd: str = "C",
    closing_cd: str = "C",
) -> Statement:
    """Create a statement for the business day with the given balances."""
    return Statement.objects.create(
        account=account,
        statement_ref="NGB261102001",
        sequence="00305/001",
        opening_cd=opening_cd,
        opening_amount=Decimal(opening_amount),
        opening_date=date(2026, 10, 30),
        closing_cd=closing_cd,
        closing_amount=Decimal(closing_amount),
        closing_date=BUSINESS_DAY,
        file_hash=uuid.uuid4().hex,
    )


def create_statement_line(
    statement: Statement,
    row_index: int,
    cd: str = "C",
    amount: str = "100.00",
    ref_ours: str = "INV1001",
    value_date: date = BUSINESS_DAY,
) -> StatementLine:
    """Create a statement line on a statement."""
    return StatementLine.objects.create(
        statement=statement,
        row_index=row_index,
        value_date=value_date,
        book_date=value_date,
        cd=cd,
        amount=Decimal(amount),
        ref_ours=ref_ours,
        ref_theirs=f"NGB{row_index:04d}",
    )


def create_ledger_entry(
    account: Account,
    entry_ref: str,
    cd: str = "D",
    amount: str = "100.00",
    ref: str = "INV1001",
    value_date: date = BUSINESS_DAY,
) -> LedgerEntry:
    """Create a ledger entry for an account."""
    return LedgerEntry.objects.create(
        account=account,
        entry_ref=entry_ref,
        value_date=value_date,
        cd=cd,
        amount=Decimal(amount),
        ref=ref,
    )


def create_match(statement_line: StatementLine, ledger_entry: LedgerEntry, state: str) -> Match:
    """Create a match linking one statement line and one ledger entry."""
    match = Match.objects.create(score=Decimal("0.850"), rule="amount_tolerance", state=state)
    match.statement_lines.add(statement_line)
    ledger_entry.match = match
    ledger_entry.save(update_fields=["match"])
    return match
