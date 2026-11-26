"""Load an MT940 statement file."""

from argparse import ArgumentParser
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from recon.exceptions import ParseError
from recon.loaders.statement import load_statement
from recon.models import Account


class Command(BaseCommand):
    help = "Load an MT940 statement for an account."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("path", type=Path)
        parser.add_argument("--account", required=True)

    def handle(self, *args: object, **options: object) -> None:
        account = Account.objects.filter(code=options["account"]).first()
        if account is None:
            raise CommandError(f"account {options['account']} not found")
        try:
            load_result = load_statement(options["path"], account)
        except (ParseError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        statement = load_result.statement
        if not load_result.created:
            self.stdout.write(f"Statement {statement.statement_ref} already loaded, nothing to do")
            return
        self.stdout.write(f"Statement        {statement.statement_ref}")
        self.stdout.write(f"Lines loaded     {load_result.line_count}")
        self.stdout.write(
            f"Opening balance  {statement.opening_cd} {statement.opening_date} "
            f"{statement.opening_amount:>16,.2f}"
        )
        self.stdout.write(
            f"Closing balance  {statement.closing_cd} {statement.closing_date} "
            f"{statement.closing_amount:>16,.2f}"
        )
