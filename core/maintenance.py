"""Data-minimisation helpers: automatic deletion of inbound messages.

purge_old_messages() removes ContactMessage rows older than the
configured retention window. It runs at most once per day, triggered
lazily by SiteConfigurationMiddleware, and can also be invoked manually:

    python manage.py purge_messages          # honour the configured window
    python manage.py purge_messages --days=0 # delete everything inbound
"""

import logging

from django.core.cache import cache
from django.utils import timezone

from core.models import CONFIG_CACHE_KEY, CONFIG_CACHE_TTL, ContactMessage, SiteConfiguration

logger = logging.getLogger(__name__)

PURGE_LAST_RUN_KEY = "core:maintenance:purge:last"
PURGE_LAST_RUN_TTL = 60 * 60 * 24


def purge_old_messages(days=None) -> int:
    """Delete contact messages older than `days` (default: the configured
    retention). Returns the number of deleted rows."""
    config = SiteConfiguration.get_solo()
    if days is None:
        days = config.message_retention_days
    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = ContactMessage.objects.filter(created__lt=cutoff).delete()
    if deleted:
        logger.info("Data minimisation: removed %d contact message(s) older than %d day(s).", deleted, days)
    return deleted


def purge_if_due() -> int:
    """Daily lazy trigger: purges only when the retention switch is on and
    the last run is more than a day old."""
    config = SiteConfiguration.get_solo()
    if not config.enable_message_auto_delete:
        return 0
    if cache.get(PURGE_LAST_RUN_KEY):
        return 0
    cache.set(PURGE_LAST_RUN_KEY, timezone.now().isoformat(), PURGE_LAST_RUN_TTL)
    return purge_old_messages()
