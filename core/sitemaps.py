"""Sitemap adapters for the shared public page registry and articles."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from core.models import Article, SiteConfiguration
from core.page_registry import public_pages


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return public_pages(SiteConfiguration.get_solo())

    def location(self, item):
        return reverse(item.route_name)

    def priority(self, item):
        return item.sitemap_priority

    def changefreq(self, item):
        return item.sitemap_changefreq

    def get_urls(self, *args, **kwargs):
        config = SiteConfiguration.get_solo()
        if not config.enable_sitemap:
            return []
        return super().get_urls(*args, **kwargs)


class ArticleSitemap(Sitemap):
    protocol = "https"
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        config = SiteConfiguration.get_solo()
        if not config.enable_sitemap or not config.enable_articles:
            return Article.objects.none()
        return Article.objects.filter(published=True)

    def lastmod(self, item):
        return item.updated_at
