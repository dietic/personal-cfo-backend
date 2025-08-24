import pytest
from httpx import AsyncClient
from fastapi import status
from app.main import app
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_usage_unauthenticated():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/v1/public/usage")
        assert r.status_code == 200
        assert r.json() == {"usage": {}}

@pytest.mark.asyncio
async def test_usage_authenticated(db_session):
    # Create user
    db: Session = db_session
    user = User(email="u1@example.com", password_hash="hash", is_active=True)
    db.add(user)
    db.commit(); db.refresh(user)
    token = create_access_token({"sub": user.email})
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/v1/public/usage", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert "cards" in body["usage"]

# Fixture for db_session might exist; if not, tests will need adaptation.
