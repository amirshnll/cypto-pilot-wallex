#!/bin/sh
set -eu

if [ "${SKIP_STARTUP_TASKS:-0}" != "1" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec gunicorn crypto_bot.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
