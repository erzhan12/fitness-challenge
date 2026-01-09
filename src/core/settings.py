import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database:
# - Dev default: SQLite at `data/db.sqlite3`
# - Prod: Postgres via `DATABASE_URL` (habit_reward-style)
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=60)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "data" / "db.sqlite3",
        }
    }

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.messages",
    "src.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = os.environ.get("TZ", "Asia/Almaty")

# Required for Django to work
# In production, set DJANGO_SECRET_KEY environment variable
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "django-insecure-fitness-challenge-local-dev-only"
)

# Debug mode (defaults to False for production safety)
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"

# Allowed hosts (comma-separated in env var)
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# URL Configuration
ROOT_URLCONF = "src.core.urls"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Static files (CSS, JavaScript, Images)
# STATIC_URL includes /admin prefix so Django templates generate correct URLs
# FastAPI serves static files at /admin/static/ to match these URLs
STATIC_URL = "/admin/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
