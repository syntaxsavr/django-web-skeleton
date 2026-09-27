"""Staff-only documentation page inside the admin: what to change where,
plus the live ops queue. This is the map for admins AND coding agents."""

from django.contrib import admin
from django.shortcuts import render

from core.models import OpsLog

ROUTING = (
    (
        "Words and images on existing pages",
        "Admin: Configuration pages + Content rows (Navigation items, Footer sections, Articles)",
        "No code. Every switch lives in the Configuration section - one page per domain, its master switch at the top. Rows live under Content.",
    ),
    (
        "New login method, consent, CSP, scraper rules, 2FA, retention windows",
        "Admin: Configuration - Accounts & login, Security & protection, Privacy & retention",
        "Security-relevant switches are deliberately NOT agent-editable. Only people change them.",
    ),
    (
        "Passwords, secrets, SMTP provider",
        ".env file on the server (DJANGO_SECRET_KEY, EMAIL_PRESET, TURNSTILE_*, OPS_SIGNING_KEY)",
        "Never in the database. Environment overrides always win over admin values.",
    ),
    (
        "New required database models or columns",
        "Code change: a normal Django migration (models.py + makemigrations)",
        "The only safe way to change the core schema. The ops-file sandbox (ai_ tables) exists for autonomous runtime additions.",
    ),
    (
        "Autonomous agent changes without a human present",
        "Ops file: signed JSON in ops/pending/ (see AGENTS.md protocol)",
        "ai_-prefixed tables and allow-listed content config only; 24h TTL; every file is logged to Ops log.",
    ),
    (
        "Layout, spacing, colors",
        "Design tokens in core/static/core/css/base.css and docs/DESIGN-SYSTEM.md",
        "Stay token-based or the dark-mode inversion and print edition break.",
    ),
    (
        "New pages or sections",
        "Code: follow AGENTS.md recipes (Add a page / Add a section)",
        "Then register the page in the sitemap routes and LLMS_PAGES.",
    ),
)


@admin.site.admin_view
def admin_docs(request):
    from core import opsmanager

    context = admin.site.each_context(request)
    context.update(
        {
            "routing": ROUTING,
            "pending": sorted(opsmanager._pending_dir().glob("*.json")),
            "recent": OpsLog.objects.all()[:10],
            "title": "How to change things",
        }
    )
    return render(request, "core/admin_docs.html", context)
