# AGENTS.md

Conventions for anyone (human or model) changing this repository. The
skeleton is derived from the gritsec-website codebase; its patterns are the
reference implementation for everything described here.

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

## Architecture map

```
skeleton/settings.py      debug/prod switch, middleware order, unfold theme
skeleton/urls.py          admin + sitemap + core include + error handlers
core/models.py            SiteConfiguration (control panel), ProtectedPage,
                          ContactMessage
core/middleware.py        the stack; read the module docstring for ordering
core/views.py             pages, lazy_section endpoint, contact defenses,
                          machine routes (llms/security), error handlers
core/context_processors.py site_settings + tracking_configuration
core/templatetags/seo_tags.py  JSON-LD + canonical helpers
core/storage.py           minify -> hash -> brotli/gzip pipeline
core/templates/core/      base.html + pages + fragments/ + account/ + legal/
core/static/core/css/     base (tokens) / components / pages / fragments
core/static/core/js/      one IIFE per concern, all deferred
.agents/skills/           design, motion, copywriting skills (+ .claude mirror)
```

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

Event bus: `lazy-section-loaded`, `lottie:complete`,
`skeleton:consent`, `skeleton:modal-open/close`.

## Recipes

### Add a page

1. Template `core/templates/core/<name>.html`: extend `base.html`, set
   `{% block page_css %}` with a file in `core/static/core/css/pages/`,
   compose sections from `core/fragments/`.
2. View in `core/views.py` (render with `page_title` and
   `meta_description` context).
3. Route in `core/urls.py` with a name.
4. Register the URL name in `core/sitemaps.py` `routes`.
5. Add it to `LLMS_PAGES` in `core/views.py` when it should appear in
   llms.txt.

### Add a section

Inline: `<section id="slug" aria-labelledby="...">` in the page. Reusable:
`core/templates/core/fragments/<slug>.html` that links its own CSS
(`core/static/core/css/fragments/<slug>.css`) as its first line, then
`{% include %}` it. Network-lazy: add `data-lazy-section` +
`data-lazy-url="{% url 'lazy_section' '<slug>' %}"`; the fragment endpoint
resolves `core/fragments/<slug>.html` (hyphen/underscore tolerant) and is
page-cached for 12 hours.

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
