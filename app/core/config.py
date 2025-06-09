from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./personalcfo.db"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OpenAI
    OPENAI_API_KEY: str = "your-openai-api-key"
    
    # Resend (Email)
    RESEND_API_KEY: str = "your-resend-api-key"
    
    # Redis (for Celery)
    REDIS_URL: str = "redis://localhost:6379"
    
    # File Storage
    UPLOAD_DIR: str = "./uploads"
    
    # App Settings
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    class Config:
        # Use absolute path to .env file
        env_file = Path(__file__).parent.parent.parent / ".env"
        env_file_encoding = 'utf-8'


settings = Settings()
