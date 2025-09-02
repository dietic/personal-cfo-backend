from fastapi import APIRouter
from app.api.v1.endpoints import auth, cards, transactions, budgets, recurring_services, statements, analytics, ai, users, categories, keywords, currencies, bank_providers, incomes, pnl
from app.api.v1.endpoints import excluded_keywords as user_excluded_keywords
from app.api.v1.endpoints import admin, public, webhooks

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(bank_providers.router, prefix="/bank-providers", tags=["bank-providers"])
api_router.include_router(cards.router, prefix="/cards", tags=["cards"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
api_router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
api_router.include_router(currencies.router, prefix="/currencies", tags=["currencies"])
api_router.include_router(incomes.router, prefix="/incomes", tags=["incomes"])
api_router.include_router(pnl.router, prefix="/pnl", tags=["profit-loss"])
api_router.include_router(recurring_services.router, prefix="/recurring-services", tags=["recurring-services"])
api_router.include_router(statements.router, prefix="/statements", tags=["statements"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(user_excluded_keywords.router, prefix="/user-settings/excluded-keywords", tags=["user-settings"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(public.router)
api_router.include_router(webhooks.router)

# Registration/waitlist public status (mock) endpoint
@api_router.get("/public/status")
async def public_status():
    return {"registration_disabled": True, "billing_ready": False}
