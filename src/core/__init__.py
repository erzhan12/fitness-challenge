import os
import django
from django.conf import settings as django_settings


def setup_django():
    """Initialize Django ORM for use with FastAPI."""
    if django_settings.configured:
        return

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.core.settings")
    django.setup()
