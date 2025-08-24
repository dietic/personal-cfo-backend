from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.core.config import settings
from app.services.mercado_pago_service import fetch_payment, create_plan_preapproval
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])  # /api/v1/webhooks

@router.post("/mercadopago")
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Mercado Pago webhooks for payment notifications."""
    try:
        payload = await request.json()
        logger.info("MP webhook received: %s", payload)

        # Handle payment notifications
        if payload.get("type") == "payment":
            payment_id = payload.get("data", {}).get("id")
            if not payment_id:
                return {"status": "ignored", "reason": "no payment id"}

            # Fetch payment details
            payment_data = await fetch_payment(str(payment_id))
            logger.info("Payment data: %s", payment_data)

            # Check if this is a plan signup payment
            metadata = payment_data.get("metadata", {})
            plan = metadata.get("plan")
            user_id = metadata.get("user_id")
            intent_type = metadata.get("intent_type")

            if not plan or intent_type != "plan_signup":
                return {"status": "ignored", "reason": "not a plan signup"}

            # Only process approved payments
            if payment_data.get("status") != "approved":
                return {"status": "ignored", "reason": f"payment status: {payment_data.get('status')}"}

            # Find user by ID
            user = None
            if user_id and user_id != "anonymous":
                user = db.query(User).filter(User.id == user_id).first()

            if not user:
                return {"status": "ignored", "reason": "user not found"}

            # Check if already upgraded
            if user.plan_tier != "free":
                return {"status": "ok", "reason": "already upgraded"}

            # Extract payer info
            payer = payment_data.get("payer", {})
            payer_email = payer.get("email")
            payer_id = payer.get("id")

            if not payer_email:
                return {"status": "error", "reason": "no payer email in payment"}

            try:
                # Create preapproval for recurring billing
                preapproval = await create_plan_preapproval(plan, payer_email)

                # Update user subscription
                user.plan_tier = plan
                user.plan_status = "active"
                user.provider_customer_id = str(payer_id) if payer_id else None
                user.provider_subscription_id = preapproval.get("id")
                user.last_payment_status = "approved"

                db.add(user)
                db.commit()

                logger.info("User %s upgraded to %s plan", user.email, plan)
                return {"status": "ok", "plan": plan, "preapproval_id": preapproval.get("id")}

            except Exception as e:
                logger.error("Failed to create preapproval for user %s: %s", user.email, str(e))
                # Still upgrade user even if preapproval fails
                user.plan_tier = plan
                user.plan_status = "active"
                user.provider_customer_id = str(payer_id) if payer_id else None
                user.last_payment_status = "approved"
                db.add(user)
                db.commit()
                return {"status": "ok", "plan": plan, "warning": "preapproval_failed"}

        return {"status": "ignored", "reason": "unhandled webhook type"}

    except Exception as e:
        logger.error("Webhook processing error: %s", str(e))
        raise HTTPException(status_code=500, detail="Webhook processing failed")
