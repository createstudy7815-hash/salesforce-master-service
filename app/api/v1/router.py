from fastapi import APIRouter
from app.api.v1.endpoints import health, credentials

api_v1_router = APIRouter()

# Health / Probe endpoints
api_v1_router.include_router(health.router, tags=["Health"])

# Salesforce Credentials endpoint
api_v1_router.include_router(credentials.router, tags=["Credentials"])
