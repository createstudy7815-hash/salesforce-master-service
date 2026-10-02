import hmac
import hashlib
import time
from typing import Optional, Set
from fastapi import Request, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from app.core.config import settings

# Memory cache for nonces to prevent replay attacks (cleared periodically)
SEEN_NONCES: Set[str] = set()
LAST_NONCE_CLEANUP = time.time()


def verify_hmac_request(
    request: Request,
    body_bytes: bytes,
    client_id: str,
    timestamp: str,
    nonce: str,
    signature: str,
    allowed_roles: Optional[list] = None
) -> dict:
    """Validate HMAC signature against canonical request string."""
    global LAST_NONCE_CLEANUP

    # 1. Clean up old nonces every 10 minutes
    now = time.time()
    if now - LAST_NONCE_CLEANUP > 600:
        SEEN_NONCES.clear()
        LAST_NONCE_CLEANUP = now

    # 2. Check timestamp freshness
    try:
        req_time = float(timestamp)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-SF-Timestamp format")

    if abs(now - req_time) > settings.HMAC_SIGNATURE_MAX_AGE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature timestamp expired")

    # 3. Check nonce replay
    nonce_key = f"{client_id}:{nonce}"
    if nonce_key in SEEN_NONCES:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nonce already used (replay attack detected)")
    SEEN_NONCES.add(nonce_key)

    # 4. Resolve client secret & role
    secret_key = None
    role = None
    if client_id == "coordinator":
        secret_key = settings.HMAC_SECRET_KEY_CORE
        role = "coordinator"
    elif client_id == "engineer":
        secret_key = settings.HMAC_SECRET_KEY_ENGINEER
        role = "engineer"
    else:
        # Default fallback to coordinator secret if configured
        secret_key = settings.HMAC_SECRET_KEY_CORE
        role = "coordinator"

    if not secret_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server HMAC key not configured")

    # Read-only role constraint
    if role == "engineer" and request.method not in ["GET", "HEAD", "OPTIONS"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer role is restricted to GET requests")

    # 5. Build canonical string: METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(BODY)
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    canonical_string = f"{request.method.upper()}\n{request.url.path}\n{timestamp}\n{nonce}\n{body_hash}"

    expected_sig = hmac.new(
        secret_key.encode("utf-8"),
        canonical_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")

    return {"client_id": client_id, "role": role}


async def hmac_auth_required(request: Request) -> dict:
    """FastAPI dependency enforcing HMAC authentication when enabled."""
    if not settings.HMAC_ENABLED:
        return {"client_id": "dev_bypass", "role": "coordinator"}

    signature = request.headers.get("X-SF-Signature")
    timestamp = request.headers.get("X-SF-Timestamp")
    client_id = request.headers.get("X-SF-Client-ID")
    nonce = request.headers.get("X-SF-Nonce")

    if not all([signature, timestamp, client_id, nonce]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required HMAC headers (X-SF-Signature, X-SF-Timestamp, X-SF-Client-ID, X-SF-Nonce)"
        )

    body = await request.body()
    return verify_hmac_request(
        request=request,
        body_bytes=body,
        client_id=client_id,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature
    )
