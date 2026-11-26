"""Load a ledger CSV export."""

from argparse import ArgumentParser
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from recon.exceptions import ParseError
from recon.loaders.ledger_csv import load_ledger_csv
from recon.models import Account


class Command(BaseCommand):
    help = "Load ledger entries from a CSV export for an account."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("path", type=Path)
        parser.add_argument("--account", required=True)

    def handle(self, *args: object, **options: object) -> None:
        account = Account.objects.filter(code=options["account"]).first()
        if account is None:
            raise CommandError(f"account {options['account']} not found")
        try:
            load_result = load_ledger_csv(options["path"], account)
        except (ParseError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Entries loaded      {load_result.loaded}")
        self.stdout.write(f"Duplicates skipped  {load_result.skipped}")
