from fastapi import APIRouter
from app.api.v1.endpoints import health, credentials, key

api_v1_router = APIRouter()

# Unauthenticated / Public probes
api_v1_router.include_router(health.router, tags=["Health"])

# Authenticated Core endpoints
api_v1_router.include_router(credentials.router, tags=["Credentials"])
api_v1_router.include_router(key.router, prefix="/key", tags=["Key"])
