"""Public page metadata shared by sitemap and machine-readable endpoints."""

from typing import NamedTuple


class PublicPage(NamedTuple):
    title: str
    route_name: str
    path: str
    description: str
    sitemap_priority: float
    sitemap_changefreq: str
    feature_flag: str = ""

    def is_enabled(self, config):
        return not self.feature_flag or bool(getattr(config, self.feature_flag))


PUBLIC_PAGES = (
    PublicPage("Home", "home", "/", "Overview of the skeleton and its patterns.", 1.0, "daily"),
    PublicPage("Demo", "demo", "/demo/", "Examples of sections, animation, consent and forms.", 0.8, "weekly"),
    PublicPage(
        "Articles",
        "articles",
        "/articles/",
        "Published articles and editorial notes.",
        0.8,
        "weekly",
        "enable_articles",
    ),
    PublicPage(
        "Contact",
        "contact",
        "/contact/",
        "Contact form with anti-spam defences.",
        0.6,
        "monthly",
        "enable_contact_form",
    ),
    PublicPage("Privacy", "privacy", "/privacy/", "Privacy policy.", 0.3, "yearly"),
    PublicPage("Imprint", "imprint", "/imprint/", "Legal imprint.", 0.3, "yearly"),
    PublicPage(
        "Accessibility",
        "accessibility",
        "/accessibility/",
        "Accessibility statement.",
        0.3,
        "yearly",
    ),
)


def public_pages(config):
    return tuple(page for page in PUBLIC_PAGES if page.is_enabled(config))
