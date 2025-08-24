import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.database import get_db
from app.models.user import User

@pytest.mark.asyncio
async def test_webhook_activation_flow(db_session):
    db: Session = db_session
    user = User(email="payer@example.com", password_hash="x", is_active=True)
    db.add(user)
    db.commit(); db.refresh(user)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {"metadata": {"plan": "plus", "payer_email": user.email}}
        r = await ac.post("/api/v1/webhooks/mercadopago", json=payload)
        assert r.status_code == 200
        db.refresh(user)
        assert user.plan_tier == "plus"
        assert user.plan_status == "active"
