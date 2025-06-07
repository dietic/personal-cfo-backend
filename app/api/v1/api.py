from fastapi import APIRouter
from app.api.v1.endpoints import auth, cards, transactions, budgets, recurring_services, statements, analytics, ai

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(cards.router, prefix="/cards", tags=["cards"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
api_router.include_router(recurring_services.router, prefix="/recurring-services", tags=["recurring-services"])
api_router.include_router(statements.router, prefix="/statements", tags=["statements"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
