"""Thresholds and tolerances for the matching engine."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MatchConfig:
    auto_threshold: Decimal = Decimal("0.95")
    review_threshold: Decimal = Decimal("0.80")
    amount_tolerance_pct: Decimal = Decimal("0.005")
    amount_tolerance_abs: Decimal = Decimal("0.00")
    date_tolerance_days: int = 0
