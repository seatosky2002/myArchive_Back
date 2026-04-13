#!/bin/bash
set -e

echo "==> Waiting for DB..."
python manage.py wait_for_db

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "==> Starting: $@"
exec "$@"
