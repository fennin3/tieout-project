from decimal import Decimal

from recon.config import MatchConfig
from recon.engine.rules import RULES, amount_tolerance, exact_amount_date, exact_amount_ref
from tests.builders import make_entry, make_line

CONFIG = MatchConfig()


def test_exact_amount_ref_scores_shared_reference() -> None:
    score = exact_amount_ref(
        make_line(refs=("INV1001", "NGB0001")), make_entry(ref="INV1001"), CONFIG
    )

    assert score == Decimal("0.99")


def test_exact_amount_ref_ignores_reference_case() -> None:
    score = exact_amount_ref(
        make_line(refs=("INV20261019", "NGB0001")), make_entry(ref=" inv20261019 "), CONFIG
    )

    assert score == Decimal("0.99")


def test_rules_score_zero_for_same_direction() -> None:
    line = make_line(cd="C")
    entry = make_entry(cd="C")

    assert [rule(line, entry, CONFIG) for rule in RULES] == [Decimal("0")] * len(RULES)


def test_exact_amount_date_scores_equal_amount_and_date() -> None:
    score = exact_amount_date(make_line(refs=("NONREF", "")), make_entry(ref=""), CONFIG)

    assert score == Decimal("0.96")


def test_amount_tolerance_scores_within_tolerance() -> None:
    score = amount_tolerance(make_line(amount="9985.00"), make_entry(amount="10000.00"), CONFIG)

    assert score == Decimal("0.85")


def test_amount_tolerance_scores_zero_outside_tolerance() -> None:
    score = amount_tolerance(make_line(amount="9940.00"), make_entry(amount="10000.00"), CONFIG)

    assert score == Decimal("0")
