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

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8000

# Copy and make startup script executable
RUN chmod +x start.sh

# Start command
CMD ["./start.sh"]