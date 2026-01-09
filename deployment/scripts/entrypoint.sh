#!/usr/bin/env sh
set -eu

# Collect static files for Django admin
python manage.py collectstatic --noinput

# Run database migrations
python manage.py migrate --noinput

exec "$@"

