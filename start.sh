#!/bin/sh
set -eu

echo "[start] collectstatic"
python manage.py collectstatic --noinput

echo "[start] migrate"
python manage.py migrate --noinput

echo "[start] cargar_instrumentos"
python manage.py cargar_instrumentos || echo "[start] AVISO: cargar_instrumentos fallo; el servidor arranca sin actualizar el catalogo"

echo "[start] gunicorn"
exec gunicorn core.wsgi --bind 0.0.0.0:${PORT:-8080}
