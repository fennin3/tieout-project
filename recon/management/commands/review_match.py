"""Approve or reject a match that is pending review."""

from argparse import ArgumentParser

from django.core.management.base import BaseCommand, CommandError

from recon.exceptions import ReviewError
from recon.services.review import review_match


class Command(BaseCommand):
    help = "Approve or reject a pending_review match."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("match_id")
        parser.add_argument("action", choices=["approve", "reject"])
        parser.add_argument("--by", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args: object, **options: str) -> None:
        try:
            match = review_match(
                options["match_id"], options["action"], options["by"], options["reason"]
            )
        except ReviewError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Match {match.id} is now {match.state}")
