from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from httpx import HTTPStatusError

from app.core.database import get_db
from app.models.waitlist_entry import WaitlistEntry
from sqlalchemy.exc import IntegrityError
from app.services.mercado_pago_service import create_plan_checkout, create_plan_checkout_intent, fetch_preapproval, fetch_preference, fetch_payment
from app.services.plan_limits import get_plan_usage
from app.core.deps import get_current_user_optional

router = APIRouter(prefix="/public", tags=["public"])

REGISTRATION_DISABLED = False
BILLING_READY = True

class StatusResponse(BaseModel):
    registration_disabled: bool
    billing_ready: bool

class WaitlistIn(BaseModel):
    email: EmailStr
    source: str | None = None

class WaitlistOut(BaseModel):
    email: EmailStr

class CheckoutRequest(BaseModel):
    plan: str
    email: EmailStr

class CheckoutResponse(BaseModel):
    init_point: str
    sandbox_init_point: str | None = None
    id: str

class UsageResponse(BaseModel):
    usage: dict

class CheckoutIntentRequest(BaseModel):
    plan: str

class CheckoutIntentResponse(BaseModel):
    init_point: str
    sandbox_init_point: str | None = None
    id: str

class SubscribeRequest(BaseModel):
    plan: str

class SubscribeResponse(BaseModel):
    init_point: str
    sandbox_init_point: str | None = None
    id: str
    message: str

@router.get("/status", response_model=StatusResponse)
async def get_status():
    return StatusResponse(registration_disabled=REGISTRATION_DISABLED, billing_ready=BILLING_READY)

@router.post("/waitlist", response_model=WaitlistOut, status_code=201)
async def add_to_waitlist(payload: WaitlistIn, db: Session = Depends(get_db)):
    entry = WaitlistEntry(email=payload.email.lower().strip(), source=payload.source)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # email already exists, return 200 OK idempotently
        return WaitlistOut(email=payload.email)
    db.refresh(entry)
    return WaitlistOut(email=entry.email)

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(payload: CheckoutRequest):
    pref = await create_plan_checkout(payload.plan, payload.email)
    return CheckoutResponse(
        init_point=pref.get("init_point"),
        sandbox_init_point=pref.get("sandbox_init_point"),
        id=pref.get("id")
    )

@router.post("/checkout-intent", response_model=CheckoutIntentResponse)
async def create_checkout_intent(payload: CheckoutIntentRequest, current_user=Depends(get_current_user_optional)):
    """Create checkout for plan signup - first month payment + recurring setup.
    After payment, webhook will activate subscription automatically.
    """
    user_id = str(current_user.id) if current_user else "anonymous"
    try:
        pref = await create_plan_checkout_intent(payload.plan, user_id)
        return CheckoutIntentResponse(
            init_point=pref.get("init_point"),
            sandbox_init_point=pref.get("sandbox_init_point"),
            id=pref.get("id")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPStatusError as e:
        mp_body = e.response.text
        raise HTTPException(status_code=400, detail=f"Mercado Pago checkout failed ({e.response.status_code}): {mp_body}")

@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(payload: SubscribeRequest, current_user=Depends(get_current_user_optional)):
    """Simple redirect to checkout-intent. Maintained for compatibility."""
    user_id = str(current_user.id) if current_user else "anonymous"
    try:
        pref = await create_plan_checkout_intent(payload.plan, user_id)
        return SubscribeResponse(
            init_point=pref.get("init_point"),
            sandbox_init_point=pref.get("sandbox_init_point"),
            id=pref.get("id"),
            message="Redirecting to payment - recurring billing will be set up after first payment"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPStatusError as e:
        mp_body = e.response.text
        raise HTTPException(status_code=400, detail=f"Mercado Pago checkout failed ({e.response.status_code}): {mp_body}")

@router.get("/preapproval/{preapproval_id}")
async def get_preapproval(preapproval_id: str):
    try:
        return await fetch_preapproval(preapproval_id)
    except HTTPStatusError as e:
        detail = {
            "error": "mercado_pago_preapproval_fetch_failed",
            "status_code": e.response.status_code,
            "mp_body": e.response.text
        }
        raise HTTPException(status_code=404, detail=detail)

@router.get("/preference/{preference_id}")
async def get_preference(preference_id: str):
    return await fetch_preference(preference_id)

@router.get("/payment/{payment_id}")
async def get_payment(payment_id: str):
    return await fetch_payment(payment_id)

@router.get("/usage", response_model=UsageResponse)
async def usage(db: Session = Depends(get_db), current_user=Depends(get_current_user_optional)):
    """Return current user usage/limits or empty if anonymous."""
    if not current_user:
        return UsageResponse(usage={})
    return UsageResponse(usage=get_plan_usage(db, current_user))
