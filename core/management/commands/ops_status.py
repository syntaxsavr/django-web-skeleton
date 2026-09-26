"""Show pending ops files and the recent ops log."""

from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import OpsLog


class Command(BaseCommand):
    help = "List pending ops files and the last log entries."

    def handle(self, *args, **options):
        pending = sorted(Path("ops", "pending").glob("*.json"))
        self.stdout.write(f"Pending files: {len(pending)}")
        for path in pending:
            self.stdout.write(f"  - {path.name}")
        for entry in OpsLog.objects.all()[:10]:
            self.stdout.write(f"{entry.processed_at:%Y-%m-%d %H:%M} {entry.status:<8} {entry.file_name} - {entry.purpose[:60]}")
