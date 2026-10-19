from fastapi import APIRouter, Depends
from app.core.hmac_auth import hmac_auth_required, HMACClient

router = APIRouter()


@router.get("/verify", tags=["Key"])
def verify_key(client: HMACClient = Depends(hmac_auth_required)):
    """
    Returns the caller's verified HMAC client identity, role, and permission profile.
    """
    return {
        "status": "authenticated",
        "client_id": client.client_id,
        "role": client.role,
        "permissions": client.permissions
    }
