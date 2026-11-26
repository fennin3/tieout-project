"""Print control-total checks for an account and business day."""

from argparse import ArgumentParser
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from recon.models import Account, Statement
from recon.reports.control_totals import build_control_totals


class Command(BaseCommand):
    help = "Print statement balance, coverage and ledger flag checks."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--account", required=True)
        parser.add_argument("--as-of", required=True, type=date.fromisoformat)

    def handle(self, *args: object, **options: object) -> None:
        account = Account.objects.filter(code=options["account"]).first()
        if account is None:
            raise CommandError(f"account {options['account']} not found")
        try:
            report = build_control_totals(account, options["as_of"])
        except Statement.DoesNotExist as exc:
            raise CommandError(
                f"no statement for {account.code} closing on or before {options['as_of']}"
            ) from exc

        self.stdout.write(
            f"Control totals for {report.account_code} as of {report.as_of_date} "
            f"(statement {report.statement_ref})"
        )
        self.stdout.write("")
        self.stdout.write(
            f"{'check':<20}  {'expected':>16}  {'actual':>16}  {'difference':>14}  result"
        )
        for check in report.checks:
            self.stdout.write(
                f"{check.name:<20}  {check.expected:>16,.2f}  {check.actual:>16,.2f}  "
                f"{check.difference:>14,.2f}  {check.status}"
            )
