from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
import os
from dotenv import load_dotenv
import logging

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.database import engine
from app.models import base
from app.core.database import SessionLocal
from app.services.seeding_service import SeedingService

# Load environment variables
load_dotenv()

# Configure audit logger (JSON lines)
audit_logger = logging.getLogger("audit")
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    # Keep raw JSON line without extra prefixes
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)
audit_logger.setLevel(logging.INFO)
# Do not propagate to root to avoid duplication
audit_logger.propagate = False

# PATCH: Apply optimized BCP extraction
def apply_bcp_extraction_patch():
    """Clean extractor is now integrated - no patch needed"""
    print("✅ Using CleanAIStatementExtractor for improved BCP extraction")

# Use clean extractor instead of patching
apply_bcp_extraction_patch()

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)

# Enhanced API description with comprehensive workflow information
api_description = """
## PersonalCFO - AI-Powered Personal Finance Management

### 🚀 Quick Start Guide

**For AI Integration & Developers:**

1. **Authentication**: Register/Login to get JWT token
2. **Categories Setup**: Ensure minimum 5 categories exist (use `/categories/create-defaults`)
3. **Statement Processing**: 3-step workflow (Upload → Extract → Categorize)
4. **Data Analysis**: Use AI endpoints for insights and categorization

### 🔑 Key Features

- **AI-Powered Transaction Categorization** - Hybrid keyword + GPT classification
- **PDF Statement Processing** - Extract transactions from bank statements
- **Real-time Budget Tracking** - Smart alerts and spending insights
- **Comprehensive Analytics** - Spending patterns and AI-generated insights

### 🤖 AI Endpoints for Integration

- `POST /ai/categorize-transaction` - Classify transactions
- `POST /ai/analyze-spending` - Generate spending insights
- `POST /ai/detect-anomalies` - Identify unusual patterns
- `POST /statements/{id}/categorize` - Bulk transaction classification

### 📋 Required Workflow for Statement Import

1. **Check Categories**: `GET /categories/validate-minimum`
2. **Upload PDF**: `POST /statements/upload`
3. **Extract Data**: `POST /statements/{id}/extract`
4. **Categorize**: `POST /statements/{id}/categorize`
5. **Monitor Status**: `GET /statements/{id}/status`

### 🔗 Complete Documentation

Visit [GitHub Repository](https://github.com/your-repo) for detailed integration guides and examples.

---
"""

app = FastAPI(
    title="PersonalCFO API",
    description=api_description,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# GZip compression for large JSON responses
app.add_middleware(GZipMiddleware, minimum_size=500)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include API router
app.include_router(api_router, prefix="/api/v1")

# --- Idempotent seeding on startup ---
@app.on_event("startup")
def seed_on_startup():
    db = SessionLocal()
    try:
        added = SeedingService.seed_bank_providers(db)
        stats = SeedingService.backfill_user_categories_and_keywords(db)
        print(f"🪴 Seeding complete: bank_providers +{added}; backfill {stats}")
    except Exception as e:
        # Do not block startup if seeding fails; just log
        print(f"⚠️ Seeding error: {e}")
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "PersonalCFO API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/debug/cors")
async def debug_cors():
    return {"cors_origins": settings.CORS_ORIGINS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
