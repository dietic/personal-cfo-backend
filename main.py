from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.database import engine
from app.models import base

# Load environment variables
load_dotenv()

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
