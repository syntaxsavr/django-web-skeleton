"""Database-level guardrails: case-insensitive unique email on auth_user
(registration and login identity must be unique where the database can
enforce it; blank emails of anonymous accounts stay valid) and cleanup of
expired magic links."""

from django.db import migrations

UNIQUE_EMAIL_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS unique_user_email_ci
ON auth_user (LOWER(email)) WHERE email <> '';
"""

DROP_UNIQUE_EMAIL_SQL = "DROP INDEX IF EXISTS unique_user_email_ci;"


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_userprofile_suspended_by_data_deletion_and_more"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(sql=UNIQUE_EMAIL_SQL, reverse_sql=DROP_UNIQUE_EMAIL_SQL),
    ]
