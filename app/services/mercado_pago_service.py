from typing import Optional
from dataclasses import dataclass
import httpx
from app.core.config import settings
import logging
import re

logger = logging.getLogger(__name__)

TEST_BUYER_REGEX = re.compile(r"^test_user_\d+@testuser\.com$")

PRODUCTION_API = "https://api.mercadopago.com"
SANDBOX_API = "https://api.mercadopago.com"

@dataclass
class PreferenceItem:
    title: str
    quantity: int
    unit_price: float  # in PEN
    currency_id: str = "PEN"

class MercadoPagoService:
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or settings.MP_ACCESS_TOKEN

        # Force test mode for development - all tokens use sandbox API
        # TEST- tokens are always sandbox, APP_USR- tokens use sandbox in development
        is_test_mode = True  # Force test mode for development
        is_test_token = (self.access_token.startswith("TEST-") or
                        self.access_token.startswith("APP_USR-") or
                        is_test_mode)
        base_api = SANDBOX_API if is_test_token else PRODUCTION_API

        logger.info(f"MercadoPago initialized with {'TEST' if is_test_token else 'PRODUCTION'} credentials")
        logger.info(f"Token prefix: {self.access_token[:10]}...")
        logger.info(f"Using API base: {base_api}")

        self._client = httpx.AsyncClient(base_url=base_api, headers={
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        })

    async def create_preference(self, items: list[PreferenceItem], payer_email: Optional[str] = None, metadata: Optional[dict] = None):
        payload = {
            "items": [
                {
                    "title": it.title,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "currency_id": it.currency_id,
                } for it in items
            ],
            "metadata": metadata or {},
            "payment_methods": {
                "excluded_payment_types": [
                    {"id": "ticket"},
                    {"id": "atm"}
                ],
                "installments": 1
            },
            "binary_mode": True,
            "back_urls": {
                "success": settings.FRONTEND_URL + "/dashboard?payment=success&plan=" + metadata.get("plan", "unknown"),
                "failure": settings.FRONTEND_URL + "/dashboard?payment=failure&plan=" + metadata.get("plan", "unknown"),
                "pending": settings.FRONTEND_URL + "/dashboard?payment=pending&plan=" + metadata.get("plan", "unknown"),
            },
            "notification_url": "https://personal-cfo.io/api/v1/webhooks/mercadopago"
        }
        try:
            resp = await self._client.post("/checkout/preferences", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            try:
                error_detail = e.response.json()
            except:
                error_detail = {"raw": e.response.text}
            logger.error(f"Mercado Pago preferences error status={e.response.status_code} payload={payload} response={error_detail}")
            raise

    async def get_preference(self, preference_id: str):
        resp = await self._client.get(f"/checkout/preferences/{preference_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_payment(self, payment_id: str):
        resp = await self._client.get(f"/v1/payments/{payment_id}")
        resp.raise_for_status()
        return resp.json()

    async def get_preapproval(self, preapproval_id: str):
        resp = await self._client.get(f"/preapproval/{preapproval_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_preapproval(self, payload: dict):
        resp = await self._client.post("/preapproval", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()

async def create_plan_checkout(plan: str, payer_email: str):
    if plan not in ("plus", "pro"):
        raise ValueError("Invalid plan tier")
    if plan == "plus":
        price = settings.PLAN_PLUS_PRICE_PEN / 100
        title = "Personal CFO Plus (Mensual)"
    else:
        price = settings.PLAN_PRO_PRICE_PEN / 100
        title = "Personal CFO Pro (Mensual)"
    svc = MercadoPagoService()
    try:
        pref = await svc.create_preference([
            PreferenceItem(title=title, quantity=1, unit_price=price)
        ], payer_email=None, metadata={"plan": plan})
    finally:
        await svc.close()
    return pref

async def create_plan_checkout_intent(plan: str, user_id: str):
    """Create checkout preference for plan signup (first month payment).
    After payment success, webhook will create preapproval for recurring billing.
    No email required - user can pay with any Mercado Pago account.
    """
    if plan not in ("plus", "pro"):
        raise ValueError("Invalid plan tier")

    if plan == "plus":
        price = settings.PLAN_PLUS_PRICE_PEN / 100
        title = "Personal CFO Plus - Primer Mes"
    else:
        price = settings.PLAN_PRO_PRICE_PEN / 100
        title = "Personal CFO Pro - Primer Mes"

    svc = MercadoPagoService()
    try:
        pref = await svc.create_preference([
            PreferenceItem(title=title, quantity=1, unit_price=price)
        ], payer_email=None, metadata={
            "plan": plan,
            "user_id": user_id,
            "intent_type": "plan_signup"
        })
        return pref
    finally:
        await svc.close()

async def create_plan_preapproval(plan: str, payer_email: str):
    """Create recurring subscription (preapproval) for a plan (monthly).
    Called after first payment to set up recurring billing.
    Requires valid payer_email from payment webhook.
    """
    if plan not in ("plus", "pro"):
        raise ValueError("Invalid plan tier")
    if not payer_email or "@" not in payer_email:
        raise ValueError("Valid payer_email required")

    if plan == "plus":
        amount = settings.PLAN_PLUS_PRICE_PEN / 100
        reason = "Personal CFO Plus (Mensual)"
    else:
        amount = settings.PLAN_PRO_PRICE_PEN / 100
        reason = "Personal CFO Pro (Mensual)"

    svc = MercadoPagoService()
    try:
        payload = {
            "reason": reason,
            "auto_recurring": {
                "frequency": 1,
                "frequency_type": "months",
                "transaction_amount": amount,
                "currency_id": "PEN"
            },
            "payer_email": payer_email.strip().lower(),
            "back_url": settings.FRONTEND_URL + "/dashboard?payment=subscription",
            "status": "pending",
            "external_reference": f"recurring:{plan}:{payer_email}"
        }
        logger.debug("Preapproval create payload=%s", payload)
        resp = await svc.create_preapproval(payload)
        return resp
    except httpx.HTTPStatusError as e:
        try:
            body = e.response.json()
        except Exception:
            body = {"raw": e.response.text}
        logger.error("Mercado Pago preapproval error status=%s body=%s", e.response.status_code, body)
        raise
    finally:
        await svc.close()

async def fetch_preapproval(preapproval_id: str):
    svc = MercadoPagoService()
    try:
        return await svc.get_preapproval(preapproval_id)
    finally:
        await svc.close()

async def fetch_preference(preference_id: str):
    svc = MercadoPagoService()
    try:
        return await svc.get_preference(preference_id)
    finally:
        await svc.close()

async def fetch_payment(payment_id: str):
    svc = MercadoPagoService()
    try:
        return await svc.get_payment(payment_id)
    finally:
        await svc.close()
