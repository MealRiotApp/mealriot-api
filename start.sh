#!/bin/bash
set -e

echo "Waiting for postgres..."
DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
DB_PORT=${DB_PORT:-5432}

while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; do
    sleep 1
done
echo "Postgres is ready."

echo "Running migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
