"""Daily maintenance: retention purges, GDPR deletions, export building,
ops-file processing. The lazy in-request trigger (core/maintenance.py)
covers low-traffic days, but this command is the sanctioned schedule:

    deploy/skeleton-daily.timer   (systemd)
    deploy/skeleton-daily.cron    (cron)

Both call:  python manage.py daily_maintenance
"""

import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the daily maintenance pass (exports, GDPR deletions, retention, ops files)."

    def handle(self, *args, **options):
        from accounts.maintenance import run_all

        results = run_all(force=True)
        self.stdout.write(json.dumps(results, default=str))
