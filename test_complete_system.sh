#!/bin/bash

# Enhanced PDF Import System Setup and Test Script
# Run this script to set up and test the enhanced PDF import functionality

echo "🚀 Enhanced PDF Import System Setup"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the backend root directory"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Please create one with: python -m venv venv"
    exit 1
fi

# Check Python and dependencies
echo ""
echo "🐍 Checking Python and dependencies..."
python --version
pip list | grep -E "(openai|fastapi|alembic|pandas|PyPDF2)" || echo "⚠️ Some dependencies may be missing"

# Validate system readiness
echo ""
echo "🔍 Validating system readiness..."
python validate_system_ready.py

# Check OpenAI API key
echo ""
echo "🔑 Checking OpenAI API key configuration..."
if grep -q "OPENAI_API_KEY=your-openai-api-key" .env; then
    echo "⚠️ OpenAI API key is still set to placeholder"
    echo "   Please update the .env file with your real OpenAI API key:"
    echo "   OPENAI_API_KEY=sk-your-actual-key-here"
    echo ""
    read -p "Do you want to continue without AI features? (y/N): " continue_without_ai
    if [[ ! $continue_without_ai =~ ^[Yy]$ ]]; then
        echo "Please set up your OpenAI API key and run this script again."
        exit 1
    fi
else
    echo "✅ OpenAI API key appears to be configured"
fi

# Run database migrations
echo ""
echo "🗄️ Running database migrations..."
alembic upgrade head
if [ $? -eq 0 ]; then
    echo "✅ Database migrations completed"
else
    echo "❌ Database migration failed"
    exit 1
fi

# Start the server in the background
echo ""
echo "🖥️ Starting FastAPI server..."
python -m uvicorn main:app --reload --port 8000 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Check if server is running
if curl -s http://localhost:8000/docs > /dev/null; then
    echo "✅ Server started successfully at http://localhost:8000"
    echo "📖 API documentation available at: http://localhost:8000/docs"
else
    echo "❌ Server failed to start"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Run the enhanced PDF import test
echo ""
echo "🧪 Running enhanced PDF import test..."
python test_enhanced_pdf_import.py

# Show results summary
echo ""
echo "📊 Test Summary"
echo "=============="
echo "✅ Server: Running on http://localhost:8000"
echo "✅ Database: Migrations applied"
echo "✅ API: Available with Swagger docs"
echo "📄 Test PDF: EECC_VISA_unlocked.pdf"

echo ""
echo "🎯 Manual Testing Steps:"
echo "1. Open http://localhost:8000/docs in your browser"
echo "2. Register a new user via /auth/register"
echo "3. Login via /auth/login to get JWT token"
echo "4. Upload PDF via /statements/upload (use Authorization header)"
echo "5. Check alerts via /alerts/ endpoints"

echo ""
echo "🛑 To stop the server, run: kill $SERVER_PID"

# Keep script running so server stays up
echo ""
echo "Press Ctrl+C to stop the server and exit..."
wait $SERVER_PID
