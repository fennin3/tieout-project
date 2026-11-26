"""Create a nostro account."""

from argparse import ArgumentParser

from django.core.management.base import BaseCommand

from recon.models import Account


class Command(BaseCommand):
    help = "Create an account, or report that it already exists."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--code", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--currency", required=True)

    def handle(self, *args: object, **options: str) -> None:
        account, created = Account.objects.get_or_create(
            code=options["code"],
            defaults={"name": options["name"], "currency": options["currency"]},
        )
        if created:
            self.stdout.write(f"Created account {account.code} ({account.currency})")
        else:
            self.stdout.write(f"Account {account.code} already exists")
