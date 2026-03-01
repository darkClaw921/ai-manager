#!/bin/bash
set -e

# Only run migrations and seed from the API process, not from worker
if echo "$@" | grep -q "uvicorn"; then
    echo "Running Alembic migrations..."
    alembic upgrade head

    echo "Running seed (idempotent)..."
    python -m app.db.seed
fi

echo "Starting application..."
exec "$@"
