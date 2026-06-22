FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PGDATA=/var/lib/postgresql/data \
    DATABASE_URL=postgresql://sentinel:sentinel@127.0.0.1:5432/sentinel

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql \
        postgresql-client \
        supervisor \
    && PG_BIN="$(ls -d /usr/lib/postgresql/*/bin | head -1)" \
    && for cmd in initdb pg_ctl psql pg_isready; do \
         ln -sf "${PG_BIN}/${cmd}" /usr/local/bin/${cmd}; \
       done \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt

COPY sentinel ./sentinel
COPY docker ./docker
COPY .env.example ./.env.example

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000 8501

VOLUME ["/var/lib/postgresql/data"]

ENTRYPOINT ["/app/docker/entrypoint.sh"]
