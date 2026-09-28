# django-web-skeleton

A Django base for building web apps fast: the repetitive parts and the EU compliance work are already integrated, everything is switchable from the admin, and the whole repository is written so coding agents can work on it safely.

> **EU GDPR: best effort, not legal advice.** The compliance machinery below is implemented and tested, but every deployment processes data differently. Have a lawyer review your instance before you rely on it. No liability is assumed.

## What is already in

- **Everything is a switch.** Articles, contact form, consent, tracking, login methods, registration, sitemap, robots.txt, llms.txt, IndexNow, embeds, middleware layers - each has a runtime switch in the admin. Disabled means absent: routes 404 and links vanish from navigation, footer, sitemap and AI files. Tested per feature.
- **Editorial system.** Articles built from ordered blocks (text, quote, image, video, Stripe buy button), hero/OG images, WebP conversion, unsaved-state preview.
- **Navigation and footer as data.** Megamenu groups and footer columns are rows - links, text, images, action buttons - with drag-and-drop ordering and a live preview of the saved site next to the editor.
- **Accounts.** Password, email code, magic link and anonymous access-code logins; registration with email confirmation and optional admin approval; optional forced 2FA. Code and magic-link flows never reveal whether an address exists.
- **GDPR machinery.** Consent-first tracking (nothing loads without opt-in), consent versioning for signup checkboxes, data exports with waiting period / retention / cooldown, scheduled data + account deletion with suspension and reversibility window, automatic purging of contact messages and login traces, optional irreversibly hashed email storage.
- **Security.** CSP derived from enabled features, honeypot + signed time-trap + rate limits + Cloudflare Turnstile on forms, scraper blocking, uniform error pages that reveal nothing, secrets via environment only, ops files for autonomous agents restricted to a sandbox.
- **SEO.** Sitemap, robots rules, JSON-LD, llms.txt / llms-full.txt for AI crawlers, IndexNow, verification meta tags - each individually switchable.

## AI-ready

Built to be worked on by coding agents, not just humans:

- **[AGENTS.md](AGENTS.md)** is the operating manual: architecture map, change routing, security invariants, recipes.
- **The admin explains itself** - every settings page says what it does and what switching off removes.
- **Signed ops files** let an autonomous agent change only allow-listed content, fully logged.
- **164 tests are the contract** - every switch is asserted in both states. `python manage.py test` defines "still works".
- Say **`init the template`** to a coding agent in this repo and it runs the one-time setup interview ([HEY-READ-THIS-FIRST.md](HEY-READ-THIS-FIRST.md)).

## Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/admin/` - the dev seed creates the superuser from `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` in `.env` (set your own before the first run). In production the seed never runs; use `createsuperuser`.

## Before shipping

```bash
python manage.py test
python manage.py collectstatic --noinput
```

Install the daily maintenance schedule from [deploy/](deploy/) (GDPR deletions and exports must not depend on traffic). The legal pages are starters - replace every placeholder. Screenshots: [docs/images](docs/images).
