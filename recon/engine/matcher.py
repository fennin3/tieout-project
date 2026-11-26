"""Greedy one-to-one assignment of statement lines to ledger entries."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from recon.config import MatchConfig
from recon.engine.rules import RULES, EntryIn, LineIn


@dataclass(frozen=True)
class Pair:
    line_id: int
    entry_id: int
    score: Decimal
    rule: str


@dataclass(frozen=True)
class MatchResult:
    auto: list[Pair]
    review: list[Pair]
    unmatched_lines: list[int]
    unmatched_entries: list[int]


def _best_pair(line: LineIn, entry: EntryIn, config: MatchConfig) -> Pair:
    best_score = Decimal("0")
    best_rule = ""
    for rule in RULES:
        score = rule(line, entry, config)
        if score > best_score:
            best_score, best_rule = score, rule.__name__
    return Pair(line_id=line.id, entry_id=entry.id, score=best_score, rule=best_rule)


def match_statement_lines(
    lines: Sequence[LineIn], entries: Sequence[EntryIn], config: MatchConfig
) -> MatchResult:
    """Pair statement lines with ledger entries by descending score, each used at most once."""
    candidates = [
        pair
        for line in lines
        for entry in entries
        if (pair := _best_pair(line, entry, config)).score >= config.review_threshold
    ]
    candidates.sort(key=lambda pair: pair.score, reverse=True)

    used_line_ids: set[int] = set()
    used_entry_ids: set[int] = set()
    auto: list[Pair] = []
    review: list[Pair] = []
    for pair in candidates:
        if pair.line_id in used_line_ids or pair.entry_id in used_entry_ids:
            continue
        used_line_ids.add(pair.line_id)
        used_entry_ids.add(pair.entry_id)
        if pair.score >= config.auto_threshold:
            auto.append(pair)
        else:
            review.append(pair)

    return MatchResult(
        auto=auto,
        review=review,
        unmatched_lines=[line.id for line in lines if line.id not in used_line_ids],
        unmatched_entries=[entry.id for entry in entries if entry.id not in used_entry_ids],
    )
