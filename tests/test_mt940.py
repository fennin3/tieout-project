from datetime import date
from decimal import Decimal

import pytest

from recon.exceptions import ParseError
from recon.parsers.mt940 import parse_mt940
from tests.builders import mt940_text


def test_parse_mt940_parses_opening_and_closing_balances() -> None:
    parsed = parse_mt940(mt940_text([], opening="C261030USD1284316,45", closing="D261102USD250,00"))

    assert (parsed.opening_cd, parsed.opening_date, parsed.opening_amount) == (
        "C",
        date(2026, 10, 30),
        Decimal("1284316.45"),
    )
    assert (parsed.closing_cd, parsed.closing_date, parsed.closing_amount) == (
        "D",
        date(2026, 11, 2),
        Decimal("250.00"),
    )


def test_parse_mt940_parses_line_with_booking_date() -> None:
    parsed = parse_mt940(mt940_text([":61:2610311102C2150,00NMSCNONREF//NGB0001"]))

    statement_line = parsed.lines[0]
    assert statement_line.value_date == date(2026, 10, 31)
    assert statement_line.book_date == date(2026, 11, 2)
    assert statement_line.cd == "C"
    assert statement_line.transaction_type == "NMSC"


def test_parse_mt940_splits_refs_on_double_slash() -> None:
    parsed = parse_mt940(mt940_text([":61:2611021102D22740,00NTRFPO/4471//NGB0007"]))

    assert parsed.lines[0].ref_ours == "PO/4471"
    assert parsed.lines[0].ref_theirs == "NGB0007"


def test_parse_mt940_attaches_narrative_to_preceding_line() -> None:
    parsed = parse_mt940(
        mt940_text(
            [
                ":61:2611021102C100,00NTRFINV1//NGB0001",
                ":86:ALDERBROOK SUPPLY INV1",
                ":61:2611021102D50,00NTRFPAY-1//NGB0002",
                ":86:BRAMWELL FREIGHT PAY-1",
            ]
        )
    )

    assert [statement_line.narrative for statement_line in parsed.lines] == [
        "ALDERBROOK SUPPLY INV1",
        "BRAMWELL FREIGHT PAY-1",
    ]


def test_parse_mt940_parses_comma_decimal_as_decimal() -> None:
    parsed = parse_mt940(
        mt940_text([":61:261102C12875,4NTRFINV1//NGB0001", ":61:261102D75,NCHGNONREF//NGB0002"])
    )

    assert [statement_line.amount for statement_line in parsed.lines] == [
        Decimal("12875.40"),
        Decimal("75.00"),
    ]
    assert all(isinstance(statement_line.amount, Decimal) for statement_line in parsed.lines)


def test_parse_mt940_rejects_unknown_tag_with_line_number() -> None:
    with pytest.raises(ParseError, match=r"line 5: unsupported tag :65:"):
        parse_mt940(mt940_text([":65:C261103USD1000,00"]))


@pytest.mark.parametrize("reversal_code", ["RC", "RD"])
def test_parse_mt940_rejects_reversal_codes(reversal_code: str) -> None:
    with pytest.raises(
        ParseError, match=rf"line 5: reversal code {reversal_code} is not supported"
    ):
        parse_mt940(mt940_text([f":61:2611021102{reversal_code}100,00NTRFINV1//NGB0001"]))
