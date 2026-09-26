"""Apply pending signed ops files (the autonomous AI change protocol)."""

from django.core.management.base import BaseCommand

from core import opsmanager


class Command(BaseCommand):
    help = "Validate and apply pending ops files from ops/pending/."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Validate only; apply nothing.")

    def handle(self, *args, **options):
        summary = opsmanager.process_pending(apply=not options["dry_run"])
        for key, value in summary.items():
            if value:
                self.stdout.write(f"{key}: {value}")
