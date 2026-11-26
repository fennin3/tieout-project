from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from recon.exceptions import ParseError
from recon.loaders.ledger_csv import load_ledger_csv
from recon.models import LedgerEntry
from tests.builders import create_account, ledger_csv_text

VALID_ROWS = [
    "JE-001,2026-11-02,D,48250.00,INV20261015,Receipt Alderbrook Supply",
    "JE-002,2026-11-02,C,15420.5,,Payment Bramwell Freight",
]


@pytest.mark.django_db
def test_load_ledger_csv_loads_valid_rows(tmp_path: Path) -> None:
    account = create_account()
    csv_path = tmp_path / "ledger.csv"
    csv_path.write_text(ledger_csv_text(VALID_ROWS), encoding="utf-8")

    load_result = load_ledger_csv(csv_path, account)

    assert (load_result.loaded, load_result.skipped) == (2, 0)
    ledger_entry = LedgerEntry.objects.get(entry_ref="JE-002")
    assert ledger_entry.value_date == date(2026, 11, 2)
    assert ledger_entry.cd == "C"
    assert ledger_entry.amount == Decimal("15420.50")
    assert ledger_entry.ref == ""
    assert ledger_entry.is_matched is False


@pytest.mark.django_db
def test_load_ledger_csv_rejects_invalid_cd_with_row_number(tmp_path: Path) -> None:
    account = create_account()
    csv_path = tmp_path / "ledger.csv"
    csv_path.write_text(
        ledger_csv_text([VALID_ROWS[0], "JE-002,2026-11-02,X,100.00,,Unknown direction"]),
        encoding="utf-8",
    )

    with pytest.raises(ParseError, match=r"row 3: invalid cd"):
        load_ledger_csv(csv_path, account)
    assert not LedgerEntry.objects.exists()


@pytest.mark.django_db
def test_load_ledger_csv_reload_adds_nothing(tmp_path: Path) -> None:
    account = create_account()
    csv_path = tmp_path / "ledger.csv"
    csv_path.write_text(ledger_csv_text(VALID_ROWS), encoding="utf-8")
    load_ledger_csv(csv_path, account)

    load_result = load_ledger_csv(csv_path, account)

    assert (load_result.loaded, load_result.skipped) == (0, 2)
    assert LedgerEntry.objects.count() == 2
