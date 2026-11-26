from decimal import Decimal

from recon.config import MatchConfig
from recon.engine.matcher import Pair, match_statement_lines
from tests.builders import make_entry, make_line

CONFIG = MatchConfig()


def test_match_statement_lines_routes_clean_pair_to_auto() -> None:
    match_result = match_statement_lines([make_line(line_id=1)], [make_entry(entry_id=7)], CONFIG)

    assert match_result.auto == [
        Pair(line_id=1, entry_id=7, score=Decimal("0.99"), rule="exact_amount_ref")
    ]
    assert match_result.review == []


def test_match_statement_lines_routes_tolerance_pair_to_review() -> None:
    match_result = match_statement_lines(
        [make_line(line_id=1, amount="9985.00")],
        [make_entry(entry_id=7, amount="10000.00")],
        CONFIG,
    )

    assert match_result.auto == []
    assert match_result.review == [
        Pair(line_id=1, entry_id=7, score=Decimal("0.85"), rule="amount_tolerance")
    ]


def test_match_statement_lines_reports_unpaired_items_as_unmatched() -> None:
    match_result = match_statement_lines(
        [make_line(line_id=1), make_line(line_id=2, cd="D", amount="75.00", refs=("NONREF", ""))],
        [make_entry(entry_id=7), make_entry(entry_id=8, cd="C", amount="950.00", ref="CHQ-1")],
        CONFIG,
    )

    assert [pair.line_id for pair in match_result.auto] == [1]
    assert match_result.unmatched_lines == [2]
    assert match_result.unmatched_entries == [8]
