#!/bin/bash
# PersonalCFO Database Initialization Script
set -e

APP_DIR="/opt/personalcfo"
APP_USER="personalcfo"

echo "🗄️ Initializing PersonalCFO database..."

# Check if .env file exists
if [ ! -f "$APP_DIR/.env" ]; then
    echo "❌ Error: .env file not found at $APP_DIR/.env"
    echo "Please copy .env.production to .env and configure your database settings"
    exit 1
fi

# Load environment variables
cd $APP_DIR
source $APP_DIR/venv/bin/activate

# Test database connection
echo "🔌 Testing database connection..."
python3 -c "
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print('❌ DATABASE_URL not found in environment')
    exit(1)

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"

# Run Alembic migrations
echo "🔄 Running database migrations..."
alembic upgrade head

# Seed initial data
echo "🌱 Seeding initial data..."
python3 -c "
from app.core.database import SessionLocal
from app.services.seeding_service import SeedingService

print('🏦 Seeding bank providers...')
db = SessionLocal()
try:
    added = SeedingService.seed_bank_providers(db)
    print(f'✅ Added {added} bank providers')
    
    stats = SeedingService.backfill_user_categories_and_keywords(db)
    print(f'✅ Backfilled user categories and keywords: {stats}')
    
finally:
    db.close()

print('✅ Database initialization completed!')
"

echo "✅ Database initialization completed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Start the application: sudo systemctl start personalcfo"
echo "2. Check the logs: sudo journalctl -u personalcfo -f"
echo "3. Test the API: curl http://localhost:8000/health"