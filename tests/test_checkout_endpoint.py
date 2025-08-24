import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_checkout_bad_plan():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/api/v1/public/checkout", json={"plan": "invalid", "email": "user@example.com"})
        assert r.status_code == 422 or r.status_code == 400

@pytest.mark.asyncio
async def test_checkout_missing_email():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/api/v1/public/checkout", json={"plan": "plus"})
        assert r.status_code in (400, 422)
