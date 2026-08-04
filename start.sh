#!/bin/sh
set -eu

echo "[start] collectstatic"
python manage.py collectstatic --noinput

echo "[start] migrate"
python manage.py migrate --noinput

echo "[start] cargar_instrumentos"
python manage.py cargar_instrumentos || echo "[start] AVISO: cargar_instrumentos fallo; el servidor arranca sin actualizar el catalogo"

echo "[start] gunicorn"
# Sin --workers, gunicorn arranca UN solo worker sync y toda la plataforma
# atiende una peticion a la vez (los usuarios hacen fila). 4 workers x 4 hilos
# = 16 peticiones concurrentes y como maximo 16 conexiones a Postgres
# (max_connections=100), con margen de sobra.
# Ajustables por variable de entorno sin tocar codigo.
exec gunicorn core.wsgi \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers ${GUNICORN_WORKERS:-4} \
    --threads ${GUNICORN_THREADS:-4} \
    --timeout 120 \
    --graceful-timeout 30 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --access-logformat '%(h)s "%(r)s" %(s)s %(b)sb %(L)ss'
