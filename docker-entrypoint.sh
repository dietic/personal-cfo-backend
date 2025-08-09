#!/usr/bin/env sh
set -e

# Run Alembic migrations
alembic upgrade head

# Start API
exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers
