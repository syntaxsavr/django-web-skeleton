# Deployment helpers

- `skeleton-daily.service` + `skeleton-daily.timer` — systemd pair that runs
  `manage.py daily_maintenance` once a day: contact-message retention, GDPR
  deletions and data-export building, login-trace purges, and processing of
  signed ops files. `Persistent=true` catches up after downtime.
- `skeleton-daily.cron` — the same schedule as a crontab line.

The site also triggers this pass lazily on the first request of the day, but
a real schedule must exist in production: GDPR deletions and export building
must not depend on visitors. Install one of the two.
