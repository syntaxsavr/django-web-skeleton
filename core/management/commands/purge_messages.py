"""Delete inbound contact messages older than the retention window.

    python manage.py purge_messages              # configured window
    python manage.py purge_messages --days=0     # wipe all inbound mail
"""

from django.core.management.base import BaseCommand, CommandError

from core.maintenance import purge_old_messages


class Command(BaseCommand):
    help = "Remove stored contact messages older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="Override the retention window.")

    def handle(self, *args, **options):
        try:
            deleted = purge_old_messages(days=options["days"])
        except ValueError as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(f"Removed {deleted} contact message(s)."))
