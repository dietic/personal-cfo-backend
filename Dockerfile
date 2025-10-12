# Backend Dockerfile for Personal-CFO (FastAPI + Python 3.12)

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY personal-cfo-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY personal-cfo-backend/ .
# Ensure old migration files are cleared before adding current ones
RUN rm -rf alembic/versions/*
COPY personal-cfo-backend/alembic/versions/ alembic/versions/

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
