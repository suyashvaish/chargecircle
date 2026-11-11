from fastapi import APIRouter
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.community import router as community_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.payments import router as payments_router
from app.api.v1.reliability import router as reliability_router
from app.api.v1.users import router as users_router
from app.api.v1.pricing import router as pricing_router
from app.api.v1.compare import router as compare_router
from app.api.v1.navigation import router as navigation_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(discovery_router)
api_router.include_router(marketplace_router)
api_router.include_router(payments_router)
api_router.include_router(reliability_router)
api_router.include_router(users_router)
api_router.include_router(community_router)
api_router.include_router(admin_router)
api_router.include_router(pricing_router)
api_router.include_router(compare_router)
api_router.include_router(navigation_router)
