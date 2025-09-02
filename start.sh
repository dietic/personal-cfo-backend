#!/bin/bash

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
while ! pg_isready -h postgres -p 5432 -U personalcfo; do
  sleep 2
done

echo "PostgreSQL is ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "Migrations applied successfully!"
else
    echo "Migrations failed!"
    exit 1
fi

# Start the application
echo "Starting application..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
