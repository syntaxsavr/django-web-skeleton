"""Move display options out of the footer: the accessibility button in the
header replaces the seeded Display footer section."""

from django.db import migrations

A11Y_ACTIONS = ("dark", "text_size", "motion", "print")


def remove_display_footer_items(apps, schema_editor):
    FooterItem = apps.get_model("core", "FooterItem")
    FooterSection = apps.get_model("core", "FooterSection")
    FooterItem.objects.filter(kind="action", action__in=A11Y_ACTIONS).delete()
    FooterSection.objects.filter(title="Display", items__isnull=True).delete()


def restore_nothing(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_siteconfiguration_announcement_text_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_display_footer_items, restore_nothing),
    ]
