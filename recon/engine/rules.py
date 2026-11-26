"""Scoring rules that compare one statement line with one ledger entry."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from recon.config import MatchConfig

NO_MATCH = Decimal("0")


@dataclass(frozen=True)
class LineIn:
    id: int
    value_date: date
    book_date: date | None
    cd: str
    amount: Decimal
    refs: tuple[str, ...]
    narrative: str


@dataclass(frozen=True)
class EntryIn:
    id: int
    value_date: date
    cd: str
    amount: Decimal
    ref: str
    narrative: str


Rule = Callable[[LineIn, EntryIn, MatchConfig], Decimal]


def _normalise_ref(ref: str) -> str:
    return ref.strip().upper()


def exact_amount_ref(line: LineIn, entry: EntryIn, config: MatchConfig) -> Decimal:
    """Score 0.99 for equal amounts where the line and entry share a non-empty reference."""
    if line.cd == entry.cd or line.amount != entry.amount:
        return NO_MATCH
    entry_ref = _normalise_ref(entry.ref)
    line_refs = {_normalise_ref(ref) for ref in line.refs}
    if entry_ref and entry_ref in line_refs:
        return Decimal("0.99")
    return NO_MATCH


def exact_amount_date(line: LineIn, entry: EntryIn, config: MatchConfig) -> Decimal:
    """Score 0.96 for equal amounts on the same value date."""
    if line.cd == entry.cd:
        return NO_MATCH
    if line.amount == entry.amount and line.value_date == entry.value_date:
        return Decimal("0.96")
    return NO_MATCH


def amount_tolerance(line: LineIn, entry: EntryIn, config: MatchConfig) -> Decimal:
    """Score same-date pairs whose amounts differ by no more than the configured tolerance."""
    if line.cd == entry.cd or line.value_date != entry.value_date:
        return NO_MATCH
    difference = abs(line.amount - entry.amount)
    tolerance = max(config.amount_tolerance_abs, config.amount_tolerance_pct * entry.amount)
    if difference > tolerance:
        return NO_MATCH
    return Decimal("0.92") if difference == 0 else Decimal("0.85")


RULES: tuple[Rule, ...] = (exact_amount_ref, exact_amount_date, amount_tolerance)
