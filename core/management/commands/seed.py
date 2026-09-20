"""Idempotent bootstrap: superuser, control panel defaults, demo protected page."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.middleware import ProtectedPageMiddleware
from core.models import ProtectedPage, SiteConfiguration


class Command(BaseCommand):
    help = "Seed the skeleton: admin user, SiteConfiguration, protected page example."

    def handle(self, *args, **options):
        User = get_user_model()

        username = settings.SEED_ADMIN_USERNAME
        password = settings.SEED_ADMIN_PASSWORD
        email = settings.SEED_ADMIN_EMAIL
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists, password unchanged."))
        else:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}' with the seeded password."))
            self.stdout.write("Change it immediately for anything reachable by others.")

        config = SiteConfiguration.get_solo()
        self.stdout.write(self.style.SUCCESS(f"SiteConfiguration ready ({config.site_name})."))

        protected, created = ProtectedPage.objects.get_or_create(
            path="/account/",
            defaults={"match_type": ProtectedPage.MATCH_PREFIX, "title": "your account", "active": True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("ProtectedPage /account/ created (login wall demo)."))
        ProtectedPageMiddleware.invalidate_cache()
