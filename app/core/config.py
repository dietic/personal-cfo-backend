from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+psycopg2://personalcfo:personalcfo@postgres:5432/personalcfo"

    # JWT
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OTP Settings
    OTP_EXP_MINUTES: int = 10
    OTP_RESEND_COOLDOWN_SECONDS: int = 30
    OTP_MAX_ATTEMPTS: int = 5
    OTP_VERIFY_MAX_PER_MINUTE: int = 5
    OTP_RESEND_MAX_PER_MINUTE: int = 3

    # OpenAI
    OPENAI_API_KEY: str = "your-openai-api-key"

    # Resend (Email)
    RESEND_API_KEY: str = "your-resend-api-key"
    EMAIL_FROM: str = "PersonalCFO <noreply@personal-cfo.io>"

    # Redis (for Celery / rate limiting)
    REDIS_URL: str = "redis://localhost:6379"

    # File Storage
    UPLOAD_DIR: str = "./uploads"

    # App Settings
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3002",
        "https://personal-cfo.io",
    ]

    # Admin seeding
    ADMIN_EMAIL: str = "dierios93@gmail.com"

    class Config:
        # Use absolute path to .env file
        env_file = Path(__file__).parent.parent.parent / ".env"
        env_file_encoding = 'utf-8'


settings = Settings()
