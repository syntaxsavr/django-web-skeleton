"""Create first-run records after the core migrations are available."""

from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.cache import cache

from core.bootstrap import ensure_admin_user, ensure_starter_content
from core.models import CONFIG_CACHE_KEY


@receiver(post_migrate, dispatch_uid="core.bootstrap_after_migrate")
def bootstrap_after_migrate(sender, **kwargs):
    if sender.name != "core":
        return
    cache.delete(CONFIG_CACHE_KEY)
    ensure_admin_user()
    ensure_starter_content()
