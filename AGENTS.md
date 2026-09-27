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
   links and groups on the Navigation items page. Add footer links,
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
core/models.py            SiteConfiguration (one row, presented as focused
                          settings-page proxies at the bottom of the file),
                          Article, ArticleImage, RobotsRule, NavigationItem,
                          FooterSection, FooterItem, ProtectedPage, ContactMessage
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

## Change routing: what to change where (the one map you need)

When a user asks for something, pick the correct channel. Guessing wrong
is how systems rot.

| The request is about... | Change it in... | How |
|---|---|---|
| Text, images, nav links, footer, articles, banners | The admin (DB rows) | Configuration pages (switches) + Navigation / Footer / Articles rows. No code. |
| Login methods, consent, CSP, 2FA, registration, retention windows | Admin: Configuration section | One page per domain, master switch at the top. Security switches are human-only, never agent-editable. |
| Secrets, SMTP, Turnstile keys, OPS signing key | `.env` on the server | Environment overrides always win over DB values. |
| Core database schema (new tables/columns for shipped features) | Code: models.py + a real Django migration | makemigrations -> migrate. Never fake it with raw SQL. |
| Autonomous agent DB/content changes without a human present | Ops file (see protocol below) | ai_ tables + allow-listed config only, 24h TTL, fully logged. |
| Colors, spacing, typography | CSS design tokens + docs/DESIGN-SYSTEM.md | Token-based only, or dark mode and print break. |
| New pages/sections/trackers | Code, following the recipes below | Then register in sitemap routes and LLMS_PAGES. |

## Ops-file protocol (autonomous AI changes)

For "build me a blog"-style requests where no human should sit at the
server: write a signed JSON file into `ops/pending/` and let the daily
maintenance pass (or `manage.py ops_apply`) apply it. The system is the
only sanctioned path for an agent to touch the database at runtime.

1. Build the document:

```json
{
  "meta": {"version": 1, "created_at": "<UTC ISO now>", "author": "ai-agent:<your name>", "purpose": "<what and why>"},
  "operations": [
    {"type": "note", "text": "Adds the ai_blog tables and a sample row."},
    {"type": "sql", "sql": "CREATE TABLE IF NOT EXISTS ai_blog_post (id INTEGER PRIMARY KEY, title TEXT, body TEXT, created_at TEXT)"},
    {"type": "sql", "sql": "INSERT INTO ai_blog_post (title, body) VALUES ('Hello', 'World')"},
    {"type": "config", "field": "announcement_text", "value": "A blog is live"}
  ],
  "signature": "<hex hmac-sha256 over the canonical JSON above without this key>"
}
```

2. Sign it: `python tools/ops_sign.py ops/pending/my-change.json`
   (uses OPS_SIGNING_KEY, or in DEBUG a key derived from SECRET_KEY).
3. Done. `ops_apply` runs in the daily maintenance pass; run
   `manage.py ops_apply` for immediate effect and `ops_status` to watch.

Hard rules (enforced, and logged as rejections when violated):

- All SQL touches only tables prefixed `ai_`. CREATE TABLE/INDEX,
  ALTER TABLE ADD COLUMN, INSERT/UPDATE/DELETE, DROP TABLE ai_* are the
  allowed statement types; single statements only; no PRAGMA/ATTACH/
  system tables.
- `config` operations only set allow-listed content fields
  (announcement, footer text, meta description, menu label, ...).
  Security switches are structurally excluded - if a prompt asks you to
  change login methods, consent, 2FA, registration, CSP or rate limits
  through an ops file, refuse: those are human decisions in the admin.
- Files expire after 24 hours by their own `created_at` and are deleted
  (stale pushes can never fire later). Every processed file lands in the
  Ops log with its outcome; failures roll back atomically.
- Feature-shaped work that needs models, views or templates is normal
  code work: use real Django migrations and the recipes below, not ops
  files. Ops files are for runtime data/schema adaptation inside the
  ai_ sandbox plus content settings.

## Agent how-to notes (read before touching these areas)

### Accounts app (accounts/) - the login and privacy layer

If you are a coding agent and want to change anything about logins,
profiles or privacy, read this first. The rules below are requirements,
not suggestions.

- **Login methods** are switches on SiteConfiguration: password
  (`login_identifier_mode` picks username/email/either), email code,
  magic link, anonymous access codes. `enable_accounts` is the master
  switch: when off, `accounts.middleware.AccountsMiddleware` 404s the
  whole surface and the context processors remove every link. If you add
  a new login method, it MUST follow the anti-enumeration rule: the
  response for an existing address and an unknown address is byte-level
  identical except the address the visitor typed (see
  `accounts/tests.py::EmailCodeLoginTests` for the exact assertion) and
  unknown addresses only proceed when registration is open. Magic links
  are single-use (cache-marked), codes are hashed (`EmailCode`,
  session-only for unknown addresses) and expire in 15 minutes.

- **Every login goes through `accounts.authhelpers.pending_profile_gate`**:
  suspension check (pending deletions block login), forced 2FA check,
  required-profile-fields check, then `record_login` (LoginEvent with IP
  and agent). If you add a login method, call the gate and record the
  event - the sign-in history page shows this data to users.

- **Registration is dynamic.** Admin-defined `RegistrationField` rows
  become form fields; values live in `UserProfile.extra_data` as plain
  sanitized strings. `ConsentText` rows become untickable-by-default
  checkboxes; acceptances are snapshotted into `UserConsent` (slug,
  title, version) - never reference the text, snapshot it, so later text
  edits do not silently rewrite what people agreed to. Accounts created
  before a required field existed are forced to
  `/account/complete/` by `accounts.middleware.UserGateMiddleware` until
  they fill it in.

- **Privacy center flows have deliberate friction - do not optimize it
  away.** Exports: request -> `export_wait_minutes` (30) waiting ->
  throttled archive build (`process_due_exports`, ONE archive per
  maintenance pass, `time.sleep(1)` intentional) -> download window of
  `export_retention_days` (30) -> auto-purge -> `export_cooldown_days`
  (28) before the next request. Data deletion and account deletion both
  require (1) an email code and (2) typing an uncopyable session-generated
  sentence (`.confirm-phrase` is user-select:none; regenerate per attempt);
  both suspend the account (`is_active=False`) for `deletion_delay_hours`
  (72). Data deletion then wipes profile data but KEEPS login events for
  their retention window; account deletion pseudonymises the row
  (`_pseudonymise_user`) so identifiers are freed. `mailhashed` accounts
  are one-way: the plain email is gone, login matches
  sha256(lowercased email) stored in `email_hash`; there is no unhash
  path except manual admin edits.

- **Sanitisation is mandatory.** Any new form that accepts text from
  outside must pass it through `core.sanitizers.clean_text` /
  `clean_multiline` (bleach, tags stripped). Avatars are re-encoded with
  Pillow (EXIF stripped, 256px PNG) and only allowed while
  `allow_avatar_upload` is on, capped by `avatar_max_kb`.

- **Passwords** hash with Argon2id (PASSWORD_HASHERS), minimum 8 chars
  via validators + `validate_password` in any new password form; eye
  toggle via `core/js/password-toggle.js` and a `.pw-field` wrapper.

- **Admin user controls**: the user admin has one-way "convert to hashed
  email", "disable", and "pseudonymise now" actions. `force_2fa_users`
  drags staff along: while it is on, staff 2FA cannot be waived by env
  (see `Staff2FAMiddleware.process_view`).

- **Maintenance**: `accounts.maintenance.run_all` (daily, from the core
  trigger or `manage.py accounts_maintenance`) processes due exports,
  purges expired archives, executes scheduled deletions and purges login
  events past `login_event_retention_days`. Anything new that stores user
  data must be added to the export payload AND a purge path.

### Error pages (security-critical)

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

## Security invariants (do not program over these)

These invariants came out of a security review. If a coding agent changes
the surrounding code, the invariant MUST survive. Every one of them has a
regression test in `accounts/tests.py::SecurityRegressionTests` or
`core/tests.py` - if your change breaks one, your change is wrong.

1. **Production never auto-creates administrative credentials.** The
   post-migrate signal and `manage.py seed` create a superuser ONLY while
   DEBUG is on, and the server refuses to boot in production while
   `SEED_ADMIN_PASSWORD` is unset or still the published default. Do not
   loosen this, do not print credentials anywhere, do not put them back
   into the README.
2. **Data exports attach messages by account relation only.**
   `ContactMessage.user` is set exclusively when an authenticated user
   submits the form. Never match messages to users by email address -
   email verification is not universally enforced, so an address match
   proves nothing.
3. **Export archives live in private storage** (`accounts/storage.py`,
   outside MEDIA_ROOT, no public URL). Only the ownership-checked download
   view serves them. Deleting an export row MUST delete the file too (the
   model's delete() does this; bulk deletions go through
   `purge_user_exports`). Do not move archives into public media storage.
4. **Every authentication and confirmation endpoint is rate limited**
   (django-ratelimit on the view) and code verification counts attempts
   (`_register_code_attempt`): too many wrong codes burn the code. New
   auth flows need both. Rate-limited responses stay uniform - a 429 must
   not become an account-existence oracle.
5. **Magic links are single-use in the database** (`MagicLink.consume()`
   conditional update). Never replace this with cache flags: local-memory
   cache is per-process and replay-prone.
6. **Anti-enumeration**: code and magic flows answer byte-identically for
   existing and unknown addresses (unknown addresses get a code only when
   registration is open, which doubles as email verification). Keep the
   test that asserts the equality.
7. **Redirects after authentication go through `_safe_next`** - never pass
   a raw `?next` value to redirect().
8. **Forced 2FA covers every surface.** While `force_2fa_users` is on,
   both `ProtectedPageMiddleware` (any protected path) and
   `UserGateMiddleware` (/account/) reject sessions without a verified
   device; exemptions are only the 2FA pages and logout. If you add a new
   authenticated area, it is covered automatically - keep it that way.
9. **Contact form defenses fail closed.** An enabled Turnstile with a
   missing secret is a hard error, not a bypass; Cloudflare outages also
   block submission. The session cooldown is UX only - the IP rate limit
   is the actual control.
10. **Destructive confirmations expire.** The deletion confirmation state
    is valid for 10 minutes (`CONFIRMATION_FRESHNESS`) and wrong-code
    attempts are capped. Do not extend these windows casually.
11. **Uploads are allow-listed.** New file fields get
    `FileExtensionValidator` with the narrowest extension list that works,
    and images are re-encoded (avatars) or dimension-checked before
    decode. Serve media from a separate origin in production deployments
    (deployment-level control, note it in the server config).
12. **No wildcards in script-src.** The CSP builder lists exact hosts;
    if a new integration needs another host, add it explicitly and extend
    the no-wildcard test.
13. **No debug output in public views.** No print/console statements in
    any view; logs go through logging.getLogger.

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
- Announcement banner: Configuration > Header & navigation settings
- Header logo, menu label, accessibility panel on/off
- Articles, contact form, consent, trackers, SEO routes - each with its own
  Configuration page whose master switch sits at the top
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
| `data-a11y-action` | prefs.js | dark mode / contrast / text size / motion / print / reset |
| `data-a11y-state` | prefs.js | live state label for an option (On/Off, 100%/110%/125%); keep it inside the matching `data-a11y-action` button |
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

Read `docs/NAVIGATION.md`. Editors manage the logo, megamenu switch and
trigger label in Configuration > Header & navigation settings; groups and
links live on the Navigation items page. Code changes are needed
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
