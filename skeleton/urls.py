"""Root URL configuration for django-web-skeleton."""

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core.sitemaps import StaticViewSitemap

sitemaps = {"static": StaticViewSitemap}

handler400 = "core.views.handler400"
handler403 = "core.views.handler403"
handler404 = "core.views.handler404"
handler500 = "core.views.handler500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("", include("core.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
