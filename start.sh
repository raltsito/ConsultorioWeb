#!/bin/sh
set -eu

echo "[start] collectstatic"
python manage.py collectstatic --noinput

echo "[start] migrate"
python manage.py migrate --noinput

echo "[start] gunicorn"
exec gunicorn core.wsgi --bind 0.0.0.0:${PORT:-8080}
