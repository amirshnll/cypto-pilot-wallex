FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system django && adduser --system --ingroup django django

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY --chown=django:django . .
RUN mkdir -p /app/staticfiles /app/data && chown -R django:django /app/staticfiles /app/data

COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

USER django
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]