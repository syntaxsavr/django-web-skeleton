"""One-time database bootstrap used after migrations and by the seed command."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from core.models import FooterItem, FooterSection, NavigationItem, ProtectedPage, RobotsRule, SiteConfiguration


def ensure_admin_user():
    User = get_user_model()
    username = settings.SEED_ADMIN_USERNAME
    user = User.objects.filter(username=username).first()
    if user:
        return user, False
    user = User.objects.create_superuser(
        username=username,
        email=settings.SEED_ADMIN_EMAIL,
        password=settings.SEED_ADMIN_PASSWORD,
    )
    return user, True


@transaction.atomic
def ensure_starter_content():
    config = SiteConfiguration.get_solo()
    navigation_defaults = (
        ("Explore", "Index", "The starting point.", NavigationItem.PAGE_HOME, 10),
        ("Explore", "Demo", "See the system in motion.", NavigationItem.PAGE_DEMO, 20),
        ("Explore", "Articles", "Read published field notes.", NavigationItem.PAGE_ARTICLES, 30),
        ("Talk to us", "Contact", "Send a direct message.", NavigationItem.PAGE_CONTACT, 40),
        ("Account", "Account", "Open your private area.", NavigationItem.PAGE_ACCOUNT, 50),
        ("Account", "Sign in", "Continue to your account.", NavigationItem.PAGE_LOGIN, 60),
        ("Account", "Register", "Create a new account.", NavigationItem.PAGE_REGISTER, 70),
        ("Account", "Sign out", "End this session.", NavigationItem.PAGE_LOGOUT, 80),
    )
    for group, label, description, page, item_order in navigation_defaults:
        NavigationItem.objects.get_or_create(
            site_configuration=config,
            page=page,
            defaults={
                "group": group,
                "label": label,
                "description": description,
                "sort_order": item_order,
                "active": True,
            },
        )
    if config.starter_content_seeded:
        return config, False

    protected, _created = ProtectedPage.objects.get_or_create(
        path="/account/",
        defaults={"match_type": ProtectedPage.MATCH_PREFIX, "title": "your account", "active": True},
    )
    if not protected.active:
        protected.active = True
        protected.save(update_fields=["active"])

    robot_defaults = (
        ("/admin/", True, 10, "Control panel"),
        ("/accounts/", True, 20, "Authentication pages"),
        ("/account/", True, 30, "Private account area"),
        ("/contact/", True, 40, "Contact details and submissions"),
        ("/privacy/", True, 50, "Privacy and personal-data page"),
        ("/imprint/", True, 60, "Legal contact details"),
        ("/accessibility/", True, 70, "Legal statement"),
        ("/static/", True, 80, "Compiled styles, scripts, fonts and images"),
        ("/media/", True, 90, "Uploaded images and files"),
        ("/api/", True, 100, "Machine endpoint prefix"),
        ("/lazy-section/", True, 110, "Fragment endpoint"),
        ("/", False, 200, "Home page, switch on to block"),
        ("/demo/", False, 210, "Demo page, switch on to block"),
        ("/articles/", False, 220, "Articles prefix, switch on to block"),
    )
    for path, active, order, note in robot_defaults:
        RobotsRule.objects.get_or_create(
            path=path,
            directive=RobotsRule.DISALLOW,
            defaults={"active": active, "sort_order": order, "note": note},
        )

    footer_defaults = (
        (
            "Site",
            10,
            (
                (FooterItem.KIND_LINK, "Index", FooterItem.PAGE_HOME, "", 10),
                (FooterItem.KIND_LINK, "Demo", FooterItem.PAGE_DEMO, "", 20),
                (FooterItem.KIND_LINK, "Articles", FooterItem.PAGE_ARTICLES, "", 30),
                (FooterItem.KIND_LINK, "Contact", FooterItem.PAGE_CONTACT, "", 40),
                (FooterItem.KIND_LINK, "Account", FooterItem.PAGE_ACCOUNT, "", 50),
                (FooterItem.KIND_LINK, "Sign in", FooterItem.PAGE_LOGIN, "", 60),
                (FooterItem.KIND_LINK, "Register", FooterItem.PAGE_REGISTER, "", 70),
                (FooterItem.KIND_ACTION, "Sign out", "", FooterItem.ACTION_LOGOUT, 80),
                (FooterItem.KIND_LINK, "Admin backend", FooterItem.PAGE_ADMIN, "", 90),
            ),
        ),
        (
            "Legal",
            20,
            (
                (FooterItem.KIND_LINK, "Privacy", FooterItem.PAGE_PRIVACY, "", 10),
                (FooterItem.KIND_LINK, "Imprint", FooterItem.PAGE_IMPRINT, "", 20),
                (FooterItem.KIND_LINK, "Accessibility", FooterItem.PAGE_ACCESSIBILITY, "", 30),
                (FooterItem.KIND_ACTION, "Cookie settings", "", FooterItem.ACTION_COOKIE, 40),
            ),
        ),
        (
            "Machine",
            30,
            (
                (FooterItem.KIND_LINK, "robots.txt", FooterItem.PAGE_ROBOTS, "", 10),
                (FooterItem.KIND_LINK, "sitemap.xml", FooterItem.PAGE_SITEMAP, "", 20),
                (FooterItem.KIND_LINK, "llms.txt", FooterItem.PAGE_LLMS, "", 30),
                (FooterItem.KIND_LINK, "llms-full.txt", FooterItem.PAGE_LLMS_FULL, "", 40),
                (FooterItem.KIND_LINK, "security.txt", FooterItem.PAGE_SECURITY, "", 50),
                (FooterItem.KIND_LINK, "humans.txt", FooterItem.PAGE_HUMANS, "", 60),
            ),
        ),
        (
            "Display",
            40,
            (
                (FooterItem.KIND_ACTION, "Dark mode", "", FooterItem.ACTION_DARK, 10),
                (FooterItem.KIND_ACTION, "Larger text", "", FooterItem.ACTION_TEXT, 20),
                (FooterItem.KIND_ACTION, "Reduce motion", "", FooterItem.ACTION_MOTION, 30),
                (FooterItem.KIND_ACTION, "Print page", "", FooterItem.ACTION_PRINT, 40),
            ),
        ),
    )
    for title, section_order, items in footer_defaults:
        section, _created = FooterSection.objects.get_or_create(
            title=title,
            defaults={"sort_order": section_order, "active": True},
        )
        for kind, label, page, action, item_order in items:
            FooterItem.objects.get_or_create(
                section=section,
                label=label,
                defaults={
                    "kind": kind,
                    "page": page,
                    "action": action,
                    "sort_order": item_order,
                    "active": True,
                },
            )
        if title == "Site":
            FooterItem.objects.get_or_create(
                section=section,
                label="syntaxsavr",
                defaults={
                    "kind": FooterItem.KIND_LINK,
                    "page": FooterItem.PAGE_CUSTOM,
                    "url": "https://github.com/syntaxsavr",
                    "sort_order": 1000,
                    "active": True,
                    "quiet": True,
                },
            )

    config.starter_content_seeded = True
    config.save(update_fields=["starter_content_seeded"])
    return config, True
