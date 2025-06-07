#!/bin/bash

# PersonalCFO Backend Development Server
echo "🚀 Starting PersonalCFO Backend Development Server"
echo "=============================================="

# Set environment variables
export DATABASE_URL="sqlite:///./personalcfo.db"

# Activate virtual environment
source venv/bin/activate

# Start the server
echo "📡 Server will be available at:"
echo "   - API: http://localhost:8000"
echo "   - Docs: http://localhost:8000/docs"
echo "   - Admin: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000
