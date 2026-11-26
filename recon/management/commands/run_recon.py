"""Run a reconciliation for one account and business day."""

from argparse import ArgumentParser
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from recon.engine.runner import run_reconciliation
from recon.models import Account


class Command(BaseCommand):
    help = "Match statement lines to ledger entries up to an as-of date."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--account", required=True)
        parser.add_argument("--as-of", required=True, type=date.fromisoformat)

    def handle(self, *args: object, **options: object) -> None:
        account = Account.objects.filter(code=options["account"]).first()
        if account is None:
            raise CommandError(f"account {options['account']} not found")

        run = run_reconciliation(account, options["as_of"])
        self.stdout.write(f"Run id        {run.pk}")
        self.stdout.write(f"Lines in      {run.lines_in}")
        self.stdout.write(f"Entries in    {run.entries_in}")
        self.stdout.write(f"Auto          {run.auto_count}")
        self.stdout.write(f"Review        {run.review_count}")
        self.stdout.write(f"Breaks        {run.break_count}")
