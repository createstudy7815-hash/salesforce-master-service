import time
import hmac
import hashlib
import logging
from typing import Optional, Dict, Set, Tuple
from pydantic import BaseModel
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class HMACClient(BaseModel):
    client_id: str
    role: str
    permissions: list[str]


class NonceCache:
    """In-memory cache for replay protection with expiration cleanup."""
    def __init__(self, max_age_seconds: int = 300):
        self.max_age_seconds = max_age_seconds
        self._nonces: Dict[str, float] = {}

    def is_seen_and_add(self, nonce: str, now: float) -> bool:
        self._cleanup(now)
        if nonce in self._nonces:
            return True
        self._nonces[nonce] = now
        return False

    def _cleanup(self, now: float) -> None:
        cutoff = now - self.max_age_seconds
        # Remove expired nonces
        self._nonces = {k: ts for k, ts in self._nonces.items() if ts >= cutoff}

    def clear(self) -> None:
        self._nonces.clear()


nonce_cache = NonceCache(max_age_seconds=settings.HMAC_SIGNATURE_MAX_AGE)


def generate_hmac_signature(
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    secret_key: str
) -> str:
    """
    Generate hex-encoded HMAC-SHA256 signature from canonical string:
    METHOD\nPATH\nTIMESTAMP\nNONCE\nSHA256(BODY)
    """
    body_hash = hashlib.sha256(body).hexdigest()
    canonical_string = f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_hash}"
    return hmac.new(secret_key.encode("utf-8"), canonical_string.encode("utf-8"), hashlib.sha256).hexdigest()


async def hmac_auth_required(
    request: Request,
    db: Session = Depends(get_db)
) -> HMACClient:
    """
    FastAPI dependency validating HMAC-SHA256 signature and role enforcement.
    Audits every outcome.
    """
    client_ip = request.client.host if request.client else "unknown"
    method = request.method.upper()
    path = request.url.path

    if not settings.HMAC_ENABLED:
        return HMACClient(
            client_id="anonymous",
            role="coordinator",
            permissions=["read", "write", "delete"]
        )

    # 1. Extract required headers
    sig = request.headers.get("X-SF-Signature")
    timestamp_str = request.headers.get("X-SF-Timestamp")
    client_id = request.headers.get("X-SF-Client-ID")
    nonce = request.headers.get("X-SF-Nonce")

    if not all([sig, timestamp_str, client_id, nonce]):
        AuditService.write_audit(
            event_category="SECURITY",
            event_type="HMAC_AUTH_MISSING_HEADERS",
            actor_client_id=client_id,
            http_method=method,
            endpoint=path,
            request_ip=client_ip,
            status_code=401,
            outcome="FAILURE",
            severity="WARNING",
            error_detail="Missing required HMAC headers (X-SF-Signature, X-SF-Timestamp, X-SF-Client-ID, X-SF-Nonce)",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required authentication headers."
        )

    # 2. Validate timestamp freshness
    try:
        req_timestamp = float(timestamp_str)
    except ValueError:
        AuditService.write_audit(
            event_category="SECURITY",
            event_type="HMAC_AUTH_INVALID_TIMESTAMP",
            actor_client_id=client_id,
            http_method=method,
            endpoint=path,
            request_ip=client_ip,
            status_code=401,
            outcome="FAILURE",
            severity="WARNING",
            error_detail=f"Invalid timestamp format: {timestamp_str}",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid timestamp."
        )

    now = time.time()
    if abs(now - req_timestamp) > settings.HMAC_SIGNATURE_MAX_AGE:
        AuditService.write_audit(
            event_category="SECURITY",
            event_type="HMAC_AUTH_EXPIRED_TIMESTAMP",
            actor_client_id=client_id,
            http_method=method,
            endpoint=path,
            request_ip=client_ip,
            status_code=401,
            outcome="FAILURE",
            severity="WARNING",
            error_detail=f"Timestamp expired or skewed. Diff: {abs(now - req_timestamp):.2f}s",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request timestamp expired or skewed beyond allowable window."
        )

    # 3. Nonce Replay Protection
    if nonce_cache.is_seen_and_add(nonce, now):
        AuditService.write_audit(
            event_category="SECURITY",
            event_type="HMAC_AUTH_REPLAY_DETECTED",
            actor_client_id=client_id,
            http_method=method,
            endpoint=path,
            request_ip=client_ip,
            status_code=401,
            outcome="FAILURE",
            severity="ERROR",
            error_detail=f"Replay detected for nonce: {nonce}",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Duplicate nonce detected (replay attack prevention)."
        )

    # 4. Resolve client secret & role
    if client_id == settings.HMAC_COORDINATOR_CLIENT_ID:
        secret_key = settings.HMAC_SECRET_KEY_CORE
        role = "coordinator"
        permissions = ["read", "write", "delete"]
    elif client_id == settings.HMAC_ENGINEER_CLIENT_ID:
        secret_key = settings.HMAC_SECRET_KEY_ENGINEER
        role = "engineer"
        permissions = ["read"]
    else:
        AuditService.write_audit(
            event_category="SECURITY",
            event_type="HMAC_AUTH_UNKNOWN_CLIENT",
            actor_client_id=client_id,
            http_method=method,
            endpoint=path,
            request_ip=client_ip,
            status_code=401,
            outcome="FAILURE",
            severity="WARNING",
            error_detail=f"Unknown HMAC client ID: {client_id}",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown client ID."
        )

    # 5. Read body and verify signature
    body = await request.body()
    expected_sig = generate_hmac_signature(
        method=method,
        path=path,
        timestamp=timestamp_str,
        nonce=nonce,
        body=body,
        secret_key=secret_key
    )

    if not hmac.compare_digest(sig.lower(), expected_sig.lower()):
        AuditService.write_audit(
            event_category="SECURITY",
            event_type="HMAC_AUTH_INVALID_SIGNATURE",
            actor_client_id=client_id,
            actor_role=role,
            http_method=method,
            endpoint=path,
            request_ip=client_ip,
            status_code=401,
            outcome="FAILURE",
            severity="WARNING",
            error_detail="Signature mismatch.",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature."
        )

    # 6. Role Enforcement: engineer is read-only (GET, HEAD, OPTIONS)
    if role == "engineer" and method not in ("GET", "HEAD", "OPTIONS"):
        AuditService.write_audit(
            event_category="SECURITY",
            event_type="HMAC_AUTH_FORBIDDEN_ROLE",
            actor_client_id=client_id,
            actor_role=role,
            http_method=method,
            endpoint=path,
            request_ip=client_ip,
            status_code=403,
            outcome="DENIED",
            severity="WARNING",
            error_detail=f"Role '{role}' is not authorized for method {method}",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: role '{role}' only has read permissions."
        )

    # 7. Record success audit log
    AuditService.write_audit(
        event_category="SECURITY",
        event_type="HMAC_AUTH_SUCCESS",
        actor_client_id=client_id,
        actor_role=role,
        http_method=method,
        endpoint=path,
        request_ip=client_ip,
        status_code=200,
        outcome="SUCCESS",
        severity="INFO",
        db=db
    )

    return HMACClient(client_id=client_id, role=role, permissions=permissions)
