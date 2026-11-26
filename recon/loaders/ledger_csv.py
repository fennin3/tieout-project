"""Load a ledger CSV export into LedgerEntry rows."""

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from recon.exceptions import ParseError
from recon.models import Account, LedgerEntry

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
EXPECTED_HEADER = ["entry_ref", "value_date", "cd", "amount", "ref", "narrative"]


@dataclass(frozen=True)
class LedgerLoadResult:
    loaded: int
    skipped: int


def load_ledger_csv(path: Path, account: Account) -> LedgerLoadResult:
    """Load ledger entries for an account, skipping entry refs that already exist."""
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(f"{path.name} is not valid UTF-8") from exc
    parsed_entries = _parse_ledger_rows(text, account)

    with transaction.atomic():
        known_refs = set(
            LedgerEntry.objects.filter(account=account).values_list("entry_ref", flat=True)
        )
        new_entries: list[LedgerEntry] = []
        skipped = 0
        for ledger_entry in parsed_entries:
            if ledger_entry.entry_ref in known_refs:
                skipped += 1
                continue
            known_refs.add(ledger_entry.entry_ref)
            new_entries.append(ledger_entry)
        LedgerEntry.objects.bulk_create(new_entries)

    logger.info(
        "loaded %d ledger entries for %s, skipped %d", len(new_entries), account.code, skipped
    )
    return LedgerLoadResult(loaded=len(new_entries), skipped=skipped)


def _parse_ledger_rows(text: str, account: Account) -> list[LedgerEntry]:
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if header != EXPECTED_HEADER:
        raise ParseError(f"row 1: expected header {','.join(EXPECTED_HEADER)}")

    ledger_entries: list[LedgerEntry] = []
    for row_number, row in enumerate(reader, start=2):
        if len(row) != len(EXPECTED_HEADER):
            raise ParseError(f"row {row_number}: expected {len(EXPECTED_HEADER)} columns")
        entry_ref, value_date, cd, amount, ref, narrative = row
        if cd not in ("C", "D"):
            raise ParseError(f"row {row_number}: invalid cd {cd!r}, expected C or D")
        ledger_entries.append(
            LedgerEntry(
                account=account,
                entry_ref=entry_ref,
                value_date=_parse_date(value_date, row_number),
                cd=cd,
                amount=_parse_amount(amount, row_number),
                ref=ref,
                narrative=narrative,
            )
        )
    return ledger_entries


def _parse_date(value: str, row_number: int) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ParseError(f"row {row_number}: invalid value_date {value!r}") from exc


def _parse_amount(value: str, row_number: int) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ParseError(f"row {row_number}: invalid amount {value!r}") from exc
    if not amount.is_finite() or amount <= 0:
        raise ParseError(f"row {row_number}: invalid amount {value!r}")
    return amount.quantize(CENT)
