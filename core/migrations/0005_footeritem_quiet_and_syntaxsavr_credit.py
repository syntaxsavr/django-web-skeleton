from django.db import migrations, models


def add_syntaxsavr_credit(apps, schema_editor):
    FooterSection = apps.get_model("core", "FooterSection")
    FooterItem = apps.get_model("core", "FooterItem")
    section, _created = FooterSection.objects.get_or_create(
        title="Site",
        defaults={"sort_order": 10, "active": True},
    )
    FooterItem.objects.get_or_create(
        section=section,
        label="syntaxsavr",
        defaults={
            "kind": "link",
            "page": "custom",
            "url": "https://github.com/syntaxsavr",
            "sort_order": 1000,
            "active": True,
            "quiet": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_article_footersection_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="footeritem",
            name="quiet",
            field=models.BooleanField(
                default=False,
                help_text="Positions this entry as a low-contrast footer credit.",
            ),
        ),
        migrations.RunPython(add_syntaxsavr_credit, migrations.RunPython.noop),
    ]
