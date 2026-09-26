"""Run the accounts maintenance passes once, immediately."""

from django.core.management.base import BaseCommand

from accounts import maintenance


class Command(BaseCommand):
    help = "Process due exports, run scheduled deletions, purge expired data."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Ignore the daily throttle.")

    def handle(self, *args, **options):
        results = maintenance.run_all(force=options["force"])
        for key, value in results.items():
            self.stdout.write(f"{key}: {value}")
