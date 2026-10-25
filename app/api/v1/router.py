from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    credentials,
    key,
    audit,
    scan,
    batch,
    normalization,
    maintenance
)

api_v1_router = APIRouter()

# Health / Probe endpoints (Public / unauthenticated)
api_v1_router.include_router(health.router, tags=["Health"])

# Salesforce Credentials endpoint
api_v1_router.include_router(credentials.router, tags=["Credentials"])

# HMAC Key verification endpoint
api_v1_router.include_router(key.router, prefix="/key", tags=["Key"])

# Audit logs and statistics
api_v1_router.include_router(audit.router, prefix="/audit", tags=["Audit"])

# Scan coordination & lifecycle endpoints
api_v1_router.include_router(scan.router, prefix="/scan", tags=["Scan"])

# Bulk API batch metadata endpoint
api_v1_router.include_router(batch.router, prefix="/batch", tags=["Batch"])

# Normalization & tabular transformation endpoints
api_v1_router.include_router(normalization.router, prefix="/normalization", tags=["Normalization"])

# Direct alias for Section 6: POST /api/normalize/{scan_id}
api_v1_router.add_api_route(
    "/normalize/{scan_id}",
    normalization.normalize_scan,
    methods=["POST"],
    tags=["Normalization"],
    summary="Trigger the clean up the data step for a run (Section 6 alias)"
)

# Maintenance & housekeeping endpoints
api_v1_router.include_router(maintenance.router, prefix="/maintenance", tags=["Maintenance"])
