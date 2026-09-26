"""Staff-only documentation page inside the admin: what to change where,
plus the live ops queue. This is the map for admins AND coding agents."""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.models import OpsLog

ROUTING = (
    (
        "Words and images on existing pages",
        "Admin: Site configuration, Navigation items, Footer sections, Articles",
        "No code. Everything is a row in the admin and takes effect immediately.",
    ),
    (
        "New login method, consent, CSP, scraper rules, 2FA, retention windows",
        "Admin: Site configuration (Auth & login methods, Retention & exports, Middleware switches)",
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
        "This is the only safe way to change the core schema. The ops-file sandbox (ai_ tables) exists for autonomous runtime additions.",
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


@staff_member_required
def admin_docs(request):
    from core import opsmanager

    return render(
        request,
        "core/admin_docs.html",
        {
            "routing": ROUTING,
            "pending": sorted(opsmanager._pending_dir().glob("*.json")),
            "recent": OpsLog.objects.all()[:10],
            "title": "How to change things",
        },
    )
