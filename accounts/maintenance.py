"""Lazy maintenance for the accounts app.

Runs from the daily trigger in core.maintenance (which the config
middleware fires). Resource-heavy work (building export archives) is
deliberately throttled: at most one archive per pass.

    python manage.py accounts_maintenance [--force]
"""

import gzip
import json
import logging
import time
from datetime import timedelta

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone

from accounts.models import DataExportRequest, LoginEvent, UserProfile
from core.maintenance import purge_old_messages
from core.models import SiteConfiguration

logger = logging.getLogger(__name__)

LAST_RUN_KEY = "accounts:maintenance:last"
LAST_RUN_TTL = 60 * 60 * 20


def process_due_exports(limit: int = 1) -> int:
    """Build archives for requests whose waiting period has passed.
    Throttled: builds at most `limit` archives per call."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    built = 0
    due = DataExportRequest.objects.filter(status=DataExportRequest.STATUS_WAITING, ready_at__lte=timezone.now())
    for request_obj in due[:limit]:
        time.sleep(1)  # yield: exports get almost no resources on purpose
        payload = _export_payload(request_obj.user)
        blob = gzip.compress(json.dumps(payload, ensure_ascii=False, indent=1, default=str).encode("utf-8"))
        name = f"export-{request_obj.user_id}-{request_obj.pk}.json.gz"
        request_obj.file.save(name, ContentFile(blob), save=False)
        request_obj.status = DataExportRequest.STATUS_READY
        request_obj.save(update_fields=["status", "file"])
        built += 1
    return built


def _export_payload(user) -> dict:
    """Everything we hold about this person, minus technical noise that
    other users could be affected by. Restrained on purpose."""
    profile = UserProfile.for_user(user)
    sections = {
        "account": {
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined,
            "is_active": user.is_active,
            "mailhashed": profile.mailhashed,
            "is_anonymous": profile.is_anonymous,
            "extra_data": profile.extra_data,
        },
        "consents": list(user.consents.values("slug", "title", "version", "accepted_at")),
        "login_events": list(
            user.login_events.values("method", "ip_address", "user_agent", "created")
        ),
        "export_requests": list(
            user.export_requests.values("status", "created", "ready_at", "expires_at")
        ),
        "contact_messages": [],
    }
    from core.models import ContactMessage

    if user.email:
        messages = ContactMessage.objects.filter(email__iexact=user.email)
        sections["contact_messages"] = list(
            messages.values("name", "email", "message", "created", "responded")
        )
    return sections


def purge_expired_exports() -> int:
    """Delete archives older than the retention window (config)."""
    config = SiteConfiguration.get_solo()
    cutoff = timezone.now() - timedelta(days=config.export_retention_days)
    purged = 0
    for request_obj in DataExportRequest.objects.filter(status=DataExportRequest.STATUS_READY, created__lt=cutoff):
        if request_obj.file:
            request_obj.file.delete(save=False)
        request_obj.status = DataExportRequest.STATUS_PURGED
        request_obj.save(update_fields=["status", "file"])
        purged += 1
    return purged


def _pseudonymise_user(user) -> None:
    """Reduce a row to an inactive shell. Identifiers are scrambled so the
    person can register again with the same address."""
    import hashlib

    digest = hashlib.sha256(str(user.pk).encode()).hexdigest()[:10]
    user.username = f"removed-{digest}"
    user.email = ""
    user.first_name = ""
    user.last_name = ""
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=["username", "email", "first_name", "last_name", "is_active", "password"])


def execute_due_deletions() -> dict:
    """Run scheduled data deletions and account deletions past their delay."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    now = timezone.now()
    result = {"data": 0, "account": 0}

    for profile in UserProfile.objects.filter(data_deletion_at__lte=now).exclude(data_deletion_at=None):
        user = profile.user
        profile.extra_data = {}
        if profile.avatar:
            profile.avatar.delete(save=False)
        profile.avatar = ""
        profile.data_deletion_at = None
        profile.data_deletion_requested = None
        profile.save(update_fields=["extra_data", "avatar", "data_deletion_at", "data_deletion_requested"])
        user.consents.all().delete()
        # Technical traces (login events) stay for their full retention
        # window; the regular login-event purge removes them later.
        user.is_active = True
        user.save(update_fields=["is_active"])
        result["data"] += 1

    for profile in UserProfile.objects.filter(account_deletion_at__lte=now).exclude(account_deletion_at=None):
        user = profile.user
        user.consents.all().delete()
        user.login_events.all().delete()
        user.export_requests.all().delete()
        if profile.avatar:
            profile.avatar.delete(save=False)
        profile.extra_data = {}
        profile.avatar = ""
        profile.account_deletion_at = None
        profile.save(update_fields=["extra_data", "avatar", "account_deletion_at"])
        _pseudonymise_user(user)
        result["account"] += 1
    return result


def purge_login_events() -> int:
    """Remove login traces past the retention window."""
    config = SiteConfiguration.get_solo()
    cutoff = timezone.now() - timedelta(days=config.login_event_retention_days)
    deleted, _ = LoginEvent.objects.filter(created__lt=cutoff).delete()
    return deleted


def run_all(force: bool = False) -> dict:
    """Daily entry point. Skips when a run happened recently, unless forced."""
    if not force and cache.get(LAST_RUN_KEY):
        return {}
    cache.set(LAST_RUN_KEY, timezone.now().isoformat(), LAST_RUN_TTL)
    results = {}
    results["messages_purged"] = purge_old_messages()
    results["exports_built"] = process_due_exports()
    results["exports_purged"] = purge_expired_exports()
    results["deletions"] = execute_due_deletions()
    results["login_events_purged"] = purge_login_events()
    logger.info("accounts maintenance: %s", results)
    return results
