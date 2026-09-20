# django-web-skeleton

A production-shaped Django skeleton with opinions. It packages the patterns
proven on gritsec-website: consent-first tracking, a full SEO suite, a
middleware stack with admin switches, lazy sections, Lottie motion, a
minified-by-default static pipeline and an admin control panel where every
feature can be enabled, disabled and configured without touching code.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional; sensible defaults in DEBUG
python manage.py migrate
python manage.py seed         # creates admin / b_4sIcPW007
python manage.py runserver
```

Open <http://127.0.0.1:8000>. The demo tour lives at `/demo/`, the control
panel at `/admin/`.

**Change the admin password before anything goes public.** The seed
credentials are for local bootstrapping only.

## The debug / production switch

One environment variable decides everything:

| `DJANGO_DEBUG` | Behavior |
|---|---|
| `True` (default) | Verbose errors, console email, plain cookies, dev secrets allowed |
| `False` | `SECRET_KEY` becomes mandatory, HSTS + SSL redirect + secure cookies + proxy header, SMTP email from env |

Deployment: `python manage.py collectstatic` then
`gunicorn skeleton.wsgi:application`. WhiteNoise serves static files with
content hashes, brotli and gzip pre-compressed.

## Control panel

Everything below is a row in the `SiteConfiguration` singleton
(Admin: "Site configuration") or a related admin-managed model:

- **Consent & tracking**: Klaro! master switch; per-tracker IDs for GTM,
  GA4, Google Ads, Meta Pixel, LinkedIn, Microsoft UET, Clarity, Hotjar,
  TikTok, Pinterest, X and self-hosted Matomo. A tracker loads only when
  the master switch is on AND its ID is set.
- **SEO**: sitemap, robots.txt, llms.txt / llms-full.txt, JSON-LD,
  IndexNow + key, search-engine verification tokens, whole-site noindex
  kill switch for staging.
- **Forms**: contact form on/off, Turnstile on/off + keys, honeypot,
  time-trap seconds, rate-limit window.
- **Auth**: public registration on/off, approval-required mode.
- **Embeds**: Cal.com, Stripe buy button.
- **Middleware**: CSP on/off, scraper block on/off, outbound link
  handling with separate UTM and modal switches.
- **Protected pages**: put any path or prefix behind login by adding a
  `ProtectedPage` row.

Environment variables override sensitive DB values (`TURNSTILE_SITE_KEY`,
`TURNSTILE_SECRET_KEY`), so production secrets never need the admin.

## What is inside

| Area | Where |
|---|---|
| Settings + switch | `skeleton/settings.py` |
| Control panel model | `core/models.py` (`SiteConfiguration`) |
| Middleware stack | `core/middleware.py` (documented ordering) |
| Views + forms | `core/views.py`, `core/forms.py` |
| SEO template tags | `core/templatetags/seo_tags.py` |
| Minifying static storage | `core/storage.py` |
| Base template shell | `core/templates/core/base.html` |
| Section fragments | `core/templates/core/fragments/` |
| Design tokens + pages CSS | `core/static/core/css/` |
| Vanilla JS modules | `core/static/core/js/` |
| Lottie runtime + demo | `core/static/core/js/lottie-mount.js`, `core/lottie/` |
| Lottie authoring script | `tools/lottie/build_demo.py` |
| Brand asset generator | `tools/generate_brand_assets.py` |
| Management commands | `core/management/commands/` (`seed`, `indexnow`) |
| Agent skills | `.agents/skills/` (+ `.claude/skills/`, `skills-lock.json`) |

Read `AGENTS.md` before changing anything: it documents the architecture,
the data-attribute contracts, and step-by-step recipes for adding pages,
sections, trackers and legal pages.

## Scripts

```bash
python manage.py seed                      # idempotent bootstrap
python manage.py indexnow [--url=/path/]   # submit URLs (needs control panel key)
python manage.py test                      # 38 smoke tests
python tools/lottie/build_demo.py          # rebuild the demo animation
python tools/generate_brand_assets.py      # rebuild favicons/og/manifest
```

## License notes

Inter is SIL OFL 1.1 (`core/static/core/css/font-inter/OFL.txt`). Klaro!
and lottie-web are vendored under their upstream licenses in
`core/static/core/vendor/`. The `copywriting` skill is MIT
(`.agents/skills/copywriting/LICENSE`).
