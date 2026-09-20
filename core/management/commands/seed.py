"""Run the same idempotent bootstrap that follows the first migration."""

from django.core.management.base import BaseCommand

from core.bootstrap import ensure_admin_user, ensure_starter_content
from core.middleware import ProtectedPageMiddleware


class Command(BaseCommand):
    help = "Seed the skeleton: admin user, SiteConfiguration, protected page example."

    def handle(self, *args, **options):
        user, created = ensure_admin_user()
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{user.username}' with the seeded password."))
            self.stdout.write("Change it immediately for anything reachable by others.")
        else:
            self.stdout.write(self.style.WARNING(f"User '{user.username}' already exists, password unchanged."))

        config, seeded = ensure_starter_content()
        self.stdout.write(self.style.SUCCESS(f"SiteConfiguration ready ({config.site_name})."))
        if seeded:
            self.stdout.write(self.style.SUCCESS("Created starter footer, robots rules and account protection."))
        ProtectedPageMiddleware.invalidate_cache()
