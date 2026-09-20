"""Root URL configuration for django-skeleton."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.views.machine import sitemap_xml

handler400 = "core.views.errors.handler400"
handler403 = "core.views.errors.handler403"
handler404 = "core.views.errors.handler404"
handler500 = "core.views.errors.handler500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap_xml, name="django.contrib.sitemaps.views.sitemap"),
    path("", include("core.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
