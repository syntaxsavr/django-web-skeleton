#!/usr/bin/env python
"""Django's command-line utility, wired to the skeleton settings package."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "skeleton.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Activate the project virtualenv and "
            "install requirements.txt first."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
