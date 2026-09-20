"""ASGI entry point (kept for future channels/websocket use)."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "skeleton.settings")
application = get_asgi_application()
