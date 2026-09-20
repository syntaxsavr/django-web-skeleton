# Build pages without rebuilding the site

The shared shell already owns the document head, navigation, footer, consent,
accessibility controls, tracking gates, external-link handling and global
scripts. A normal page supplies only the content inside `<main>`.

## Put each concern in one place

| Change | Location |
|---|---|
| Small public page view | `core/views/pages.py` |
| Views for an existing feature | Matching module in `core/views/` |
| Views for a new feature area | New `core/views/<feature>.py` module |
| URL | `core/urls.py` |
| Public page discovery metadata | `core/page_registry.py` |
| Page template | `core/templates/core/<name>.html` |
| Reusable template section | `core/templates/core/fragments/<name>.html` |
| Page-only CSS | `core/static/core/css/pages/<name>.css` |
| Reusable section CSS | `core/static/core/css/fragments/<name>.css` |
| Feature switch | `SiteConfiguration` in `core/models.py`, then `core/admin.py` |
| Footer content | `FooterSection` and `FooterItem` records |
| Starter records | `core/bootstrap.py` |
| Tests | `core/tests.py`, split into a feature test module when that file becomes unwieldy |

Do not put feature logic in `core/views/__init__.py`, `base.html`, a context
processor or a URL file. Those files connect parts; they do not own product
behaviour.

## Add a straightforward page

Create a view in `core/views/pages.py`:

```python
def services(request):
    return render(
        request,
        "core/services.html",
        {
            "page_title": "Services",
            "meta_description": "A direct description of this page.",
        },
    )
```

Register it in `core/urls.py`:

```python
path("services/", page_views.services, name="services"),
```

Add one `PublicPage` record to `core/page_registry.py`. That single record
feeds both the sitemap and the two `llms` endpoints.

Create `core/templates/core/services.html`:

```django
{% extends "core/base.html" %}
{% load static %}
{% block page_css %}<link rel="stylesheet" href="{% static 'core/css/pages/services.css' %}">{% endblock %}
{% block content %}
<section class="services-hero" aria-labelledby="services-heading">
  <div class="shell">
    <h1 id="services-heading">Services</h1>
  </div>
</section>
{% endblock %}
```

That page automatically receives the shared navigation, footer, metadata,
consent system and global scripts. Do not copy any of those into the page.

## Add a switchable feature

Use a separate view module when a feature has its own model, form, security
rules, endpoints or more than two related views. Keep private helpers in that
module. Move reusable business logic into `core/services/<feature>.py` if it
must run outside HTTP requests too.

Every public feature follows the same contract:

1. Add one switch to `SiteConfiguration` and expose it in the admin.
2. Reject disabled routes with `Http404` before queries or other work.
3. Add its public index to `core/page_registry.py` with `feature_flag` set.
4. Hide its header and automatic footer entries with the same switch.
5. Add starter footer or robots records in `core/bootstrap.py`, never in a template.
6. Test the enabled and disabled states. The disabled test must cover the route, navigation, footer, sitemap and `llms` output.

Disabled means absent. Do not redirect a disabled public feature to another
page, advertise it, query its records or leave a dead link.

## Keep request work cheap

- Read configuration through `site_config(request)` from `core/views/helpers.py`.
  Middleware has already attached the cached singleton to the request.
- Filter and shape querysets in the owning view module. Use `select_related()`
  and `prefetch_related()` before templates cause repeated queries.
- Fetch only published or otherwise visible records. Do not load a table and
  filter it in Python.
- Cache public fragments or expensive read-only responses at the narrowest
  useful boundary. Do not cache personalised pages.
- Keep network calls outside page rendering where possible. When unavoidable,
  set a short timeout and define failure behaviour.
- Keep imports free of database queries and other side effects.
- Let unexpected template and application errors surface. Catch only the
  exceptions the view can handle correctly.
- Put browser behaviour in one deferred ES5-compatible IIFE per concern. Keep
  scripts CSP-safe and load them through template blocks.

## Keep modules small

`core/views/` is split by responsibility:

```text
pages.py       small public pages
articles.py    article publishing
contact.py     contact flow and anti-spam checks
auth.py        login, registration and account pages
machine.py     robots, sitemap, llms and IndexNow
fragments.py   cached lazy fragments
legal.py       legal and policy pages
errors.py      HTTP error pages
helpers.py     tiny shared view helpers
```

Do not create another catch-all view file. If a module starts mixing two
feature areas, split it. If a function does not read a request or return a
response, it probably belongs in a model, form, service or utility module.

## Finish the change

Run:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Then search the rendered templates for links to any feature you switched off.
The absence contract matters as much as the working page.
