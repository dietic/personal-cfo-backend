from fastapi import APIRouter
from app.api.v1.endpoints import auth, cards, transactions, budgets, recurring_services, statements, analytics, ai, alerts, users, billing, categories, keywords, currencies, bank_providers, network_providers, card_types

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(bank_providers.router, prefix="/bank-providers", tags=["bank-providers"])
api_router.include_router(network_providers.router, prefix="/network-providers", tags=["network-providers"])
api_router.include_router(card_types.router, prefix="/card-types", tags=["card-types"])
api_router.include_router(cards.router, prefix="/cards", tags=["cards"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(keywords.router, prefix="/keywords", tags=["keywords"])
api_router.include_router(budgets.router, prefix="/budgets", tags=["budgets"])
api_router.include_router(currencies.router, prefix="/currencies", tags=["currencies"])
api_router.include_router(recurring_services.router, prefix="/recurring-services", tags=["recurring-services"])
api_router.include_router(statements.router, prefix="/statements", tags=["statements"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
