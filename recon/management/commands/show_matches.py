"""List the matches created by a reconciliation run."""

from argparse import ArgumentParser

from django.core.management.base import BaseCommand, CommandError

from recon.models import Match, ReconRun

HEADER = (
    f"{'id':<8}  {'state':<14}  {'score':>5}  {'rule':<17}  {'line ref':<16}  "
    f"{'entry ref':<14}  {'line amount':>13}  {'entry amount':>13}  {'line date':<10}  "
    f"{'entry date':<10}  line narrative | entry narrative"
)


class Command(BaseCommand):
    help = "Show matches created by a reconciliation run."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--run", required=True, type=int)
        parser.add_argument("--state", choices=Match.State.values)

    def handle(self, *args: object, **options: object) -> None:
        run = ReconRun.objects.select_related("account").filter(pk=options["run"]).first()
        if run is None:
            raise CommandError(f"run {options['run']} not found")
        if run.finished_at is None:
            raise CommandError(f"run {run.pk} has not finished")

        # Matches carry no run reference, so a run's matches are those created during it.
        matches = (
            Match.objects.filter(
                created_at__gte=run.started_at,
                created_at__lte=run.finished_at,
                statement_lines__statement__account=run.account,
            )
            .distinct()
            .prefetch_related("statement_lines", "ledger_entries")
            .order_by("created_at")
        )
        if options["state"]:
            matches = matches.filter(state=options["state"])

        self.stdout.write(HEADER)
        for match in matches:
            statement_line = next(iter(match.statement_lines.all()), None)
            ledger_entry = next(iter(match.ledger_entries.all()), None)
            self.stdout.write(
                f"{str(match.id)[:8]:<8}  {match.state:<14}  {match.score:>5}  {match.rule:<17}  "
                f"{statement_line.ref_ours if statement_line else '-':<16}  "
                f"{ledger_entry.entry_ref if ledger_entry else '-':<14}  "
                f"{statement_line.amount if statement_line else '-':>13}  "
                f"{ledger_entry.amount if ledger_entry else '-':>13}  "
                f"{str(statement_line.value_date) if statement_line else '-':<10}  "
                f"{str(ledger_entry.value_date) if ledger_entry else '-':<10}  "
                f"{statement_line.narrative if statement_line else '-'} | "
                f"{ledger_entry.narrative if ledger_entry else '-'}"
            )
