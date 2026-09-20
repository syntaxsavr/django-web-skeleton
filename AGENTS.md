# AGENTS.md

Conventions for anyone (human or model) changing this repository. The
skeleton is derived from the gritsec-website codebase; its patterns are the
reference implementation for everything described here.

## One-time initialisation

If `HEY-READ-THIS-FIRST.md` exists and the user says "init the template", read
and follow it before other project work. It contains the short discovery flow,
`.env` setup, design and motion brief, consent decisions, verification steps,
and its own deletion rule. Do not delete it before the initialisation succeeds.

## Ground rules

1. **No comments in public output.** Templates may use `{# #}` and
   `{% comment %}` (never rendered). CSS/JS may carry maintainer comments
   because `collectstatic` strips them (`core/storage.py`). Never ship
   HTML comments, console.log calls or meta generators.
2. **No build step.** Vanilla deferred IIFE JavaScript, plain CSS with
   custom properties, Django templates. Do not introduce bundlers,
   TypeScript or npm.
3. **ES5-compatible, CSP-safe.** No inline scripts, no inline event
   handlers. Data flows to JS through `data-*` attributes,
   `json_script` blocks and CustomEvents.
4. **Copy discipline.** No em dashes in any copy. Follow the
   `copywriting` skill in `.agents/skills/copywriting/`. UI copy is
   short, concrete, in sentence case.
5. **Every feature is switchable.** New features get a boolean (or ID
   field) on `SiteConfiguration` plus admin wiring, and must degrade to
   a no-op when switched off. Tests assert both states.
6. **Disabled means absent.** A disabled public feature must return 404 and
   disappear from header navigation, footer records, sitemap output and
   llms page lists. Do not leave dead links or promotional references.
7. **Never hardcode navigation or footer content.** `base.html` only renders
   `NavigationItem`, `FooterSection` and `FooterItem` records. Add megamenu
   links and groups through the Site configuration inline. Add footer links,
   categories, actions, text and logos through the footer models.
8. **Keep views feature-owned.** Never recreate `core/views.py` or place
   behaviour in `core/views/__init__.py`. Add a focused module under
   `core/views/`. Read `docs/PAGE-BUILDING.md` before adding a page or route.
9. **Build only the page body.** Public templates extend `core/base.html` and
   fill `{% block content %}`. Do not duplicate the head, navigation, footer,
   consent markup or global scripts.

## Architecture map

```
skeleton/settings.py      debug/prod switch, middleware order, unfold theme
skeleton/urls.py          admin + sitemap + core include + error handlers
core/models.py            SiteConfiguration, Article, ArticleImage,
                          RobotsRule, NavigationItem, FooterSection, FooterItem,
                          ProtectedPage, ContactMessage
core/bootstrap.py         first-run admin, robots, footer and protected-page data
core/middleware.py        the stack; read the module docstring for ordering
core/views/               focused HTTP modules; one feature area per file
core/page_registry.py     sitemap + llms metadata for public pages
core/context_processors.py site_settings + tracking_configuration
core/templatetags/seo_tags.py  JSON-LD + canonical helpers
core/storage.py           minify -> hash -> brotli/gzip pipeline
core/templates/core/      base.html + pages + fragments/ + account/ + legal/
core/static/core/css/     base (tokens) / components / pages / fragments
core/static/core/js/      one IIFE per concern, all deferred
docs/PAGE-BUILDING.md     exact placement and page-building contract
docs/NAVIGATION.md        header logo, megamenu and mobile navigation contract
.agents/skills/           design, motion, copywriting skills (+ .claude mirror)
```

## Agent how-to notes (read before touching these areas)

If you are a coding agent and want to change anything below, follow the
recipe instead of inventing your own approach. These systems interact;
the notes say how.

- **Error pages (security-critical).** If you need to change how errors
  look, edit `core/templates/core/404.html` only. In production every
  failure (403, 400, CSRF, 500) renders that exact page with status 404
  through `core/views/errors.py`; do not reintroduce distinct pages,
  status codes or exception messages, and do not remove the random
  `error_padding` (it defeats response-length fingerprinting). If you
  need to block someone, raise `PermissionDenied` from a `process_view`
  (NOT a bare 403 response and NOT from middleware `__call__` - Django
  only converts exceptions raised in process_view, and bare 403s leak
  details). Password-reset and registration responses are already
  uniform; keep it that way and never reveal whether an email exists.

- **Stored messages (data minimisation).** Contact messages self-delete
  after `message_retention_days` (admin) via the lazy daily trigger in
  `SiteConfigurationMiddleware` (`core/maintenance.py`). If you add any
  NEW inbound-message or form-submission model, add it to
  `purge_old_messages()` and extend the tests - inbound data must not
  live longer than the retention window by default.

- **Email sending.** Do not hand-wire SMTP settings into code. Pick
  `EMAIL_PRESET` (ionos, outlook, microsoft365, gmail, posteo, webde,
  gmx, mailbox, mailgun, sendgrid, brevo, strato) in `.env` and add
  credentials; explicit `EMAIL_HOST`/`EMAIL_PORT`/`EMAIL_USE_TLS`
  variables override presets. In DEBUG mail goes to the console. To send
  mail from a new feature use `send_mail` and read recipients from
  SiteConfiguration, never from env-only constants.

- **Email OTP for registration.** The `enable_email_otp` switch
  (control panel) makes registration create an inactive user, email a
  six-digit code (hashed in `EmailCode`, 15-minute TTL) and require
  confirmation at `/accounts/register/confirm/`. If you build another
  flow that needs email proof, reuse `EmailCode` with a new `purpose`
  value and the helpers in `core/views/auth.py` (`_issue_otp`,
  `_hash_code`) instead of inventing a second mechanism.

- **Passwords.** Minimum length lives in `AUTH_PASSWORD_VALIDATORS`
  (min_length 8) and registration runs `validate_password` inside
  `RegistrationForm.clean_password1`. If you add a password field
  anywhere, attach the eye toggle: `core/js/password-toggle.js` plus a
  `data-password-view="<input-id>"` button inside a `.pw-field` wrapper.

- **Admin overview.** The sidebar groups come from `UNFOLD["SIDEBAR"]`
  in `skeleton/settings.py` and badges from small functions in
  `core/admin.py`. When you register a new model, add it to the matching
  group there instead of letting it fall into the default app dump.

## Two-factor enforcement

`ENFORCE_STAFF_2FA` (settings, defaults to `not DEBUG`) forces every
staff member through a TOTP second factor before `/admin/` opens.
`core.middleware.Staff2FAMiddleware` redirects unverified staff to
`/account/two-factor/setup/` (no device) or `.../verify/` (device
exists); `/admin/logout/` stays reachable. Enrollment lives in
`core/views/twofa.py` (django-otp TOTPDevice + qrcode QR). Non-staff
enrollment is optional. The seeded admin therefore needs one extra
step after the first production login; that is by design.

## Autonomy levers (fast client changes without deploys)

Everything below is editable in the admin while the site is live:
- Navigation items (megamenu groups) and footer sections/entries
- Announcement banner: Site configuration, "Announcement" fieldset
- Header logo, menu label, accessibility panel on/off
- Articles, contact form, consent, trackers, SEO routes
Prefer extending these systems over new hardcoded templates when the
change is content-shaped.

## Middleware ordering (why it matters)

```
Security -> CSP -> SiteConfig -> ScraperBlock -> SearchIndexing
-> WhiteNoise -> GZip -> ConditionalGet -> Session -> Language(optional)
-> Common -> CSRF -> Auth -> ProtectedPage -> Messages -> XFrame
-> ExternalLink
```

- `SiteConfigurationMiddleware` early: everything below reads
  `request.site_config` (one cached DB hit per request).
- `ProtectedPageMiddleware` after `AuthenticationMiddleware`: it needs
  `request.user`.
- `ExternalLinkMiddleware` last (innermost): it rewrites the final HTML;
  gzip sits outside it so the rewritten bytes get compressed. It drops
  Content-Length/ETag when it mutates a response.
- WhiteNoise before the response rewriters but after the early guards:
  static files bypass the expensive layers when served directly.

Admin paths are exempt from CSP and link rewriting (Django admin ships
its own trusted inline scripts).

## Data-attribute contracts

| Attribute | Owner | Meaning |
|---|---|---|
| `data-lazy-section` + `data-lazy-url` | lazy-sections.js | fetch fragment on approach |
| `data-lottie`, `data-lottie-loop`, `data-lottie-speed`, `data-lottie-scroll`, `data-lottie-ratio` | lottie-mount.js | declarative animation mount |
| `data-hero-entrance` / `data-hero-item` | hero-entrance.js | load choreography |
| `data-reveal` (`mask`, `left`, `scale`) | scroll-reveal.js | scroll entrance |
| `data-track="name"` | track.js | consent-gated analytics event |
| `data-external` (added by middleware) | external-link-modal.js | leave-site interception |
| `data-consent-suppress` on `<body>` | klaro-bootstrap.js | never auto-open the banner (legal pages) |
| `data-open-cookie-settings` | klaro-config.js | re-open the consent UI |
| `data-a11y-action` | prefs.js | dark mode / text size / motion toggles |
| `data-nav-toggle` + `data-site-navigation` | topbar.js | megamenu and mobile navigation state |
| `data-modal-open="<element-id>"` | modal.js | opens any dialog by id (accessibility button uses it) |

Event bus: `lazy-section-loaded`, `lottie:complete`,
`skeleton:consent`, `skeleton:modal-open/close`.

## Recipes

### Add a page

Follow `docs/PAGE-BUILDING.md`. The short version:

1. Extend `core/base.html`; write only the content block and page-specific
   CSS. Shared chrome stays shared.
2. Put the view in the matching `core/views/<feature>.py` module. Tiny
   standalone pages belong in `core/views/pages.py`.
3. Add the named route to `core/urls.py`.
4. Add its metadata once in `core/page_registry.py`; sitemap and llms output
   both read that registry.
5. Wire optional header and automatic footer links to the same feature flag.
6. Test both switch states when the page is optional.

### Add or change navigation

Read `docs/NAVIGATION.md`. Editors manage the logo, megamenu switch, trigger
label, groups and links inside Site configuration. Code changes are needed
only when a new automatic page destination is introduced.

1. Add the destination to `NavigationItem.PAGE_CHOICES`.
2. Add its route to `core.context_processors.NAVIGATION_ROUTES`.
3. Bind optional pages to their switch in `_navigation_item_visible()`.
4. Add starter navigation records in `core/bootstrap.py`.
5. Test the enabled and disabled states. Disabled destinations must leave no
   header link behind.

### Add or change footer content

Do not add footer links or columns to `base.html`.

1. Use `FooterSection` for an ordered column.
2. Use `FooterItem` for a link, action, text block or uploaded logo.
3. Add new automatic destinations to `FooterItem.PAGE_CHOICES`,
   `core.context_processors.PAGE_ROUTES` and its visibility checks.
4. Add starter records in `core/bootstrap.py` only. They are inserted once.
5. Prove feature-bound entries disappear when their switch is off.

### Add article media

Hero and Open Graph images live on `Article`. Body images are ordered
`ArticleImage` rows. The admin file fields support click-to-upload and drag
and drop. Public templates must keep alt text and credits attached.

### Add a robots rule

Use Robots rules in the admin. Rules are ordered and individually active.
Paths follow robots prefix matching, so `/media/` covers every uploaded file.
Do not edit a robots template; `core.views.machine.robots_txt` owns the response.

### Add a section

Inline: `<section id="slug" aria-labelledby="...">` in the page. Reusable:
`core/templates/core/fragments/<slug>.html` that links its own CSS
(`core/static/core/css/fragments/<slug>.css`) as its first line, then
`{% include %}` it. Network-lazy: add `data-lazy-section` +
`data-lazy-url="{% url 'lazy_section' '<slug>' %}"`; the fragment endpoint
resolves `core/fragments/<slug>.html` (hyphen/underscore tolerant) and is
page-cached for 12 hours.

### Article block editor

Articles render `ArticleBlock` rows when they exist and fall back to the
legacy plain-text `content` field otherwise. Block kinds: heading, text,
quote, image (references an uploaded ArticleImage), video (internal file
or external YouTube/Vimeo URL), Stripe buy button, divider. In the admin
the blocks inline supports drag-and-drop plus move buttons
(`core/js/admin/article-editor.js`), and the submit row has a Preview
button that POSTs the current editor state to `/articles/preview/`
(staff-only, noindex, nothing is saved). Newly uploaded article images
become WebP automatically while `enable_webp_conversion` is on
(quality: `webp_quality` field, `WEBP_QUALITY` env override). External
videos and Stripe buttons render only after the visitor consents to the
matching Klaro service (`youtube`, `vimeo`, `stripe`); with the consent
manager switched off they embed directly. CSP frame hosts for those
providers extend themselves while `enable_articles` is on.

### Add a tracker

1. ID field on `SiteConfiguration` + admin fieldset entry.
2. Expose it in `SiteConfiguration.tracking_data()` (camelCase key).
3. Declare the service + loader in `core/static/core/js/klaro-config.js`
   (`LOADERS` map, purposes: analytics or marketing).
4. Add the host to the CSP tables in `core/middleware.py`
   (`ContentSecurityPolicyMiddleware.SCRIPT_HOSTS` etc.).

A tracker with an empty ID must never be declared to the consent UI.

### Add a protected (login-only) area

Admin: Protected pages, add row, choose exact path or prefix. No code.
Rules are cache-invalidated on save.

### Add a legal page

Template in `core/templates/core/legal/`, route in `core/urls.py`, then add
the path to `PERSONAL_DATA_PATH_PREFIXES` in `core/middleware.py` so it
gets noindex, scraper blocking and consent suppression. Replace the TODO
placeholders with real content before launch.

### Rebrand

Edit `BRAND_NAME`, `BG`, `ACCENT` in `tools/generate_brand_assets.py` and
rerun it; set `site_name` / `canonical_origin` / theme color in the admin;
swap the Inter files (keep the OFL notice) or point `--font-sans` at your
own family.

## Testing expectations

`python manage.py test` covers: page smoke, machine routes, every control
panel switch (both states), CSP dynamic host extension, scraper block,
protected pages, registration toggles, contact defenses (honeypot,
time-trap, rate limit, Turnstile accept/reject), outbound link rewriting,
seed idempotency. When you add a switch, add a test that proves both
states.

Tests inherit `ConfigIsolatedTestCase` when they touch the control panel:
it clears the locmem cache between tests because transactions do not roll
back `get_solo()` caching, and it resets django-ratelimit counters.

## Skills

`.agents/skills/` (mirrored in `.claude/skills/`, pinned in
`skills-lock.json`): `frontend-design`, `animations`, `motion-design`,
`web-design-guidelines`, `vercel-react-*` (reference only; this project
has no React), `copywriting` (em-dash-free, AI-tell-free writing; read it
before writing any prose).

Design authority: `docs/DESIGN-SYSTEM.md`. When design and code disagree,
the design system wins; update both together.
