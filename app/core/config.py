from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path


class Settings(BaseSettings):
    # Database - defaults to local Docker, override with environment variable for production
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

    # Redis (for rate limiting) - defaults to local, override for production
    REDIS_URL: str = "redis://localhost:6379"

    # File Storage
    UPLOAD_DIR: str = "./uploads"

    # App Settings
    DEBUG: bool = True
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "https://personal-cfo.io",
        "https://api.personal-cfo.io",
        "https://personal-cfo-frontend-kjqe2x9er-personal-cfo.vercel.app",
        "https://personal-cfo-frontend.vercel.app",
    ]
    # URL of the frontend used for redirects/back_urls in payment flows
    # Loaded from env FRONTEND_URL when available, defaults to local nginx/next
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Admin seeding (provide via environment; do not hardcode secrets)
    ADMIN_EMAIL: str = ""
    ADMIN_BYPASS_TOKEN: str = ""
    
    # First admin user creation (auto-created on first startup)
    FIRST_ADMIN_EMAIL: str = "admin@personal-cfo.io"
    FIRST_ADMIN_PASSWORD: str = "ChangeMe123!"

    # Mercado Pago (supply via environment)
    MP_PUBLIC_KEY: str
    MP_ACCESS_TOKEN: str
    MP_TEST_BUYER_EMAIL: str | None = None
    MP_TEST_SELLER_EMAIL: str | None = None

    # Plan pricing in PEN (integer cents) supplied via env
    PLAN_PLUS_PRICE_PEN: int
    PLAN_PRO_PRICE_PEN: int

    class Config:
        # Use absolute path to .env file
        env_file = Path(__file__).parent.parent.parent / ".env"
        env_file_encoding = 'utf-8'


settings = Settings()
