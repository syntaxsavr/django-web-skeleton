"""Sitemap registry. Add a URL name here and the page enters sitemap.xml."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from core.models import SiteConfiguration


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    routes = (
        ("home", 1.0, "daily"),
        ("demo", 0.8, "weekly"),
        ("contact", 0.6, "monthly"),
        ("privacy", 0.3, "yearly"),
        ("imprint", 0.3, "yearly"),
        ("accessibility", 0.3, "yearly"),
    )

    def items(self):
        return [name for name, _p, _f in self.routes]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return dict((name, prio) for name, prio, _f in self.routes).get(item, 0.5)

    def changefreq(self, item):
        return dict((name, freq) for name, _p, freq in self.routes).get(item, "weekly")

    def get_urls(self, *args, **kwargs):
        config = SiteConfiguration.get_solo()
        if not config.enable_sitemap:
            return []
        return super().get_urls(*args, **kwargs)
