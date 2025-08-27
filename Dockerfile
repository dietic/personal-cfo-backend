# Backend Dockerfile for Personal-CFO

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system deps for building wheels where needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install deps first (better caching)
COPY personal-cfo-backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app source (only backend folder)
COPY personal-cfo-backend/ /app

# Remove only obsolete duplicate baseline migrations (keep new ones including billing/waitlist)
RUN find /app/alembic/versions -type f -name '*merge_heads_for_is_admin.py' -delete || true

# Expose uploads dir and alembic
ENV UPLOAD_DIR=/app/uploads
RUN mkdir -p "$UPLOAD_DIR"

# Default: rely on DATABASE_URL from environment
# Alembic reads settings.DATABASE_URL via env.py

EXPOSE 8000

COPY personal-cfo-backend/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Run Alembic migrations then launch API
CMD ["/app/docker-entrypoint.sh"]
