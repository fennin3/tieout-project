"""Run a reconciliation for one account and persist matches and breaks."""

import logging
from datetime import date

from django.db import transaction
from django.utils import timezone

from recon.config import MatchConfig
from recon.engine.matcher import match_statement_lines
from recon.engine.rules import EntryIn, LineIn
from recon.models import Account, Break, LedgerEntry, Match, ReconRun, StatementLine

logger = logging.getLogger(__name__)

MATCH_CONFIG = MatchConfig()


def run_reconciliation(account: Account, as_of_date: date) -> ReconRun:
    """Match unreconciled items up to as_of_date and record the run, matches and breaks."""
    run = ReconRun.objects.create(
        account=account, as_of_date=as_of_date, state=ReconRun.State.RUNNING
    )
    try:
        with transaction.atomic():
            _reconcile(run)
    except Exception as exc:
        run.state = ReconRun.State.FAILED
        run.finished_at = timezone.now()
        run.error = f"{type(exc).__name__}: {exc}"
        run.save(update_fields=["state", "finished_at", "error"])
        raise
    return run


def _reconcile(run: ReconRun) -> None:
    statement_lines = {
        statement_line.id: statement_line
        for statement_line in StatementLine.objects.filter(
            statement__account=run.account,
            value_date__lte=run.as_of_date,
            matches__isnull=True,
        ).order_by("id")
    }
    ledger_entries = {
        ledger_entry.id: ledger_entry
        for ledger_entry in LedgerEntry.objects.filter(
            account=run.account, value_date__lte=run.as_of_date, is_matched=False
        ).order_by("id")
    }

    match_result = match_statement_lines(
        [
            LineIn(
                id=statement_line.id,
                value_date=statement_line.value_date,
                book_date=statement_line.book_date,
                cd=statement_line.cd,
                amount=statement_line.amount,
                refs=(statement_line.ref_ours, statement_line.ref_theirs),
                narrative=statement_line.narrative,
            )
            for statement_line in statement_lines.values()
        ],
        [
            EntryIn(
                id=ledger_entry.id,
                value_date=ledger_entry.value_date,
                cd=ledger_entry.cd,
                amount=ledger_entry.amount,
                ref=ledger_entry.ref,
                narrative=ledger_entry.narrative,
            )
            for ledger_entry in ledger_entries.values()
        ],
        MATCH_CONFIG,
    )

    now = timezone.now()
    for pair in match_result.auto:
        match = Match.objects.create(score=pair.score, rule=pair.rule, state=Match.State.AUTO)
        match.statement_lines.add(statement_lines[pair.line_id])
        ledger_entry = ledger_entries[pair.entry_id]
        ledger_entry.match = match
        ledger_entry.is_matched = True
        ledger_entry.matched_at = now
        ledger_entry.save(update_fields=["match", "is_matched", "matched_at"])

    for pair in match_result.review:
        match = Match.objects.create(
            score=pair.score, rule=pair.rule, state=Match.State.PENDING_REVIEW
        )
        match.statement_lines.add(statement_lines[pair.line_id])
        ledger_entry = ledger_entries[pair.entry_id]
        ledger_entry.match = match
        ledger_entry.save(update_fields=["match"])

    Break.objects.bulk_create(
        [
            Break(
                run=run,
                side=Break.Side.STATEMENT,
                statement_line=statement_lines[line_id],
                state=Break.State.OPEN,
            )
            for line_id in match_result.unmatched_lines
        ]
        + [
            Break(
                run=run,
                side=Break.Side.LEDGER,
                ledger_entry=ledger_entries[entry_id],
                state=Break.State.OPEN,
            )
            for entry_id in match_result.unmatched_entries
        ]
    )

    # Syncs the flag for entries linked to a match in earlier runs.
    LedgerEntry.objects.filter(account=run.account, match__isnull=False).update(
        is_matched=True, matched_at=now
    )

    run.lines_in = len(statement_lines)
    run.entries_in = len(ledger_entries)
    run.auto_count = len(match_result.auto)
    run.review_count = len(match_result.review)
    run.break_count = len(match_result.unmatched_lines) + len(match_result.unmatched_entries)
    run.state = ReconRun.State.SUCCEEDED
    run.finished_at = timezone.now()
    run.save()

    logger.info(
        "recon run %s for %s as of %s: lines_in=%d entries_in=%d auto=%d review=%d breaks=%d",
        run.pk,
        run.account.code,
        run.as_of_date,
        run.lines_in,
        run.entries_in,
        run.auto_count,
        run.review_count,
        run.break_count,
    )
