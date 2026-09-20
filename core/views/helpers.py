"""Small helpers shared across view modules."""

from core.models import SiteConfiguration


def site_config(request):
    return getattr(request, "site_config", None) or SiteConfiguration.get_solo()
