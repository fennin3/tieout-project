"""Parser for single-account MT940 customer statements."""

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal

from recon.exceptions import ParseError

CENT = Decimal("0.01")
SUPPORTED_TAGS = frozenset({"20", "25", "28C", "60F", "61", "86", "62F"})
REQUIRED_TEXT_TAGS = ("20", "25", "28C")

TAG_PATTERN = re.compile(r"^:(?P<tag>\d{2}[A-Z]?):(?P<value>.*)$")
BALANCE_PATTERN = re.compile(
    r"^(?P<cd>[CD])(?P<date>\d{6})(?P<currency>[A-Z]{3})(?P<amount>\d+,\d*)$"
)
STATEMENT_LINE_PATTERN = re.compile(
    r"^(?P<value_date>\d{6})(?P<book_date>\d{4})?(?P<cd>R?[CD])(?P<amount>\d+,\d*)"
    r"(?P<transaction_type>[A-Z][A-Z0-9]{3})(?P<refs>.*)$"
)


@dataclass(frozen=True)
class ParsedLine:
    value_date: date
    book_date: date | None
    cd: str
    amount: Decimal
    transaction_type: str
    ref_ours: str
    ref_theirs: str
    narrative: str = ""


@dataclass(frozen=True)
class ParsedStatement:
    statement_ref: str
    account: str
    sequence: str
    opening_cd: str
    opening_date: date
    opening_amount: Decimal
    closing_cd: str
    closing_date: date
    closing_amount: Decimal
    lines: tuple[ParsedLine, ...]


@dataclass(frozen=True)
class _Balance:
    cd: str
    balance_date: date
    amount: Decimal


def parse_mt940(text: str) -> ParsedStatement:
    """Parse MT940 text into a ParsedStatement, raising ParseError on unsupported content."""
    text_fields: dict[str, str] = {}
    balances: dict[str, _Balance] = {}
    statement_lines: list[ParsedLine] = []
    previous_tag: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        tag_match = TAG_PATTERN.match(raw_line.strip())
        if tag_match is None:
            raise ParseError(f"line {line_number}: expected a field tag such as :61:")
        tag, value = tag_match["tag"], tag_match["value"].strip()
        if tag not in SUPPORTED_TAGS:
            raise ParseError(f"line {line_number}: unsupported tag :{tag}:")

        if tag == "61":
            statement_lines.append(_parse_statement_line(value, line_number))
        elif tag == "86":
            if previous_tag != "61":
                raise ParseError(f"line {line_number}: :86: must follow a :61: line")
            statement_lines[-1] = replace(statement_lines[-1], narrative=value)
        elif tag in ("60F", "62F"):
            balances[tag] = _parse_balance(value, line_number)
        else:
            text_fields[tag] = value
        previous_tag = tag

    for tag in REQUIRED_TEXT_TAGS:
        if tag not in text_fields:
            raise ParseError(f"missing :{tag}: field")
    for tag in ("60F", "62F"):
        if tag not in balances:
            raise ParseError(f"missing :{tag}: field")

    opening, closing = balances["60F"], balances["62F"]
    return ParsedStatement(
        statement_ref=text_fields["20"],
        account=text_fields["25"],
        sequence=text_fields["28C"],
        opening_cd=opening.cd,
        opening_date=opening.balance_date,
        opening_amount=opening.amount,
        closing_cd=closing.cd,
        closing_date=closing.balance_date,
        closing_amount=closing.amount,
        lines=tuple(statement_lines),
    )


def _parse_balance(value: str, line_number: int) -> _Balance:
    balance_match = BALANCE_PATTERN.match(value)
    if balance_match is None:
        raise ParseError(f"line {line_number}: invalid balance field")
    return _Balance(
        cd=balance_match["cd"],
        balance_date=_parse_yymmdd(balance_match["date"], line_number),
        amount=_parse_amount(balance_match["amount"]),
    )


def _parse_statement_line(value: str, line_number: int) -> ParsedLine:
    line_match = STATEMENT_LINE_PATTERN.match(value)
    if line_match is None:
        raise ParseError(f"line {line_number}: invalid :61: field")
    cd = line_match["cd"]
    if cd in ("RC", "RD"):
        raise ParseError(f"line {line_number}: reversal code {cd} is not supported")

    value_date = _parse_yymmdd(line_match["value_date"], line_number)
    book_date = None
    if line_match["book_date"]:
        book_date = _parse_booking_date(line_match["book_date"], value_date, line_number)
    ref_ours, _, ref_theirs = line_match["refs"].partition("//")
    return ParsedLine(
        value_date=value_date,
        book_date=book_date,
        cd=cd,
        amount=_parse_amount(line_match["amount"]),
        transaction_type=line_match["transaction_type"],
        ref_ours=ref_ours,
        ref_theirs=ref_theirs,
    )


def _parse_yymmdd(value: str, line_number: int) -> date:
    try:
        return datetime.strptime(value, "%y%m%d").date()
    except ValueError as exc:
        raise ParseError(f"line {line_number}: invalid date {value}") from exc


def _parse_booking_date(mmdd: str, value_date: date, line_number: int) -> date:
    # The booking date carries no year, so it takes the value date's year and rolls
    # across a year boundary when that would put it more than six months away.
    try:
        book_date = date(value_date.year, int(mmdd[:2]), int(mmdd[2:]))
        months_apart = (book_date.year - value_date.year) * 12 + book_date.month - value_date.month
        if months_apart > 6:
            book_date = book_date.replace(year=book_date.year - 1)
        elif months_apart < -6:
            book_date = book_date.replace(year=book_date.year + 1)
    except ValueError as exc:
        raise ParseError(f"line {line_number}: invalid booking date {mmdd}") from exc
    return book_date


def _parse_amount(value: str) -> Decimal:
    return Decimal(value.replace(",", ".")).quantize(CENT)
