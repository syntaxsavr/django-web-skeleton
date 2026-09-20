"""Context processors: expose the control panel to every template."""

from core.models import SiteConfiguration


def site_settings(request):
    config = getattr(request, "site_config", None) or SiteConfiguration.get_solo()
    return {
        "site_config": config,
        "site_name": config.site_name,
        "canonical_origin": config.canonical_origin.rstrip("/"),
        "turnstile_site_key": config.effective_turnstile_site_key if config.enable_turnstile else "",
        "turnstile_on": config.enable_turnstile,
        "enable_honeypot": config.enable_honeypot,
        "enable_registration": config.enable_public_registration,
        "enable_tracking": config.enable_tracking,
        "enable_consent": config.enable_cookie_consent,
        "enable_external_link_modal": config.enable_external_link_handling and config.external_link_modal,
        "protected_title": request.session.get("protected_page_title", ""),
    }


def tracking_configuration(request):
    config = getattr(request, "site_config", None) or SiteConfiguration.get_solo()
    return {"tracking": config, "tracking_data": config.tracking_data()}
