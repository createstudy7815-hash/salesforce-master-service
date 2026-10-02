from fastapi import APIRouter, Depends
from app.core.security import hmac_auth_required

router = APIRouter()


@router.get("/verify", tags=["Key"])
def verify_key(auth_identity: dict = Depends(hmac_auth_required)):
    """Returns caller's HMAC client identity and permission profile."""
    return {
        "status": "valid",
        "client_id": auth_identity.get("client_id"),
        "role": auth_identity.get("role"),
        "permissions": "full_access" if auth_identity.get("role") == "coordinator" else "read_only"
    }
