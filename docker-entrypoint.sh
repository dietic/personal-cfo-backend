#!/usr/bin/env sh
set -e

# Run Alembic migrations
alembic upgrade heads

# Start API
exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers
