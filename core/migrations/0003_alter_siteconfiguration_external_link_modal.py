from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_alter_siteconfiguration_theme_color"),
    ]

    operations = [
        migrations.AlterField(
            model_name="siteconfiguration",
            name="external_link_modal",
            field=models.BooleanField(
                default=True,
                help_text="Show the leave-site confirmation modal for outbound clicks.",
            ),
        ),
    ]
