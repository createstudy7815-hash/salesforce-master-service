import json
import logging
from typing import Any, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.dlq import FailedExternalCall

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "password",
    "client_secret",
    "security_token",
    "access_token",
    "jwt_key",
    "jwt_key_path",
    "secret",
    "private_key",
    "token",
    "authorization",
    "x-sf-signature"
}


def scrub_payload(payload: Any) -> Any:
    """
    Recursively scrub sensitive credential fields from dictionaries, lists, or strings.
    """
    if payload is None:
        return None
    
    if isinstance(payload, dict):
        scrubbed = {}
        for k, v in payload.items():
            if str(k).lower() in SENSITIVE_KEYS:
                scrubbed[k] = "******"
            else:
                scrubbed[k] = scrub_payload(v)
        return scrubbed
    
    if isinstance(payload, list):
        return [scrub_payload(item) for item in payload]
    
    if hasattr(payload, "model_dump"):
        return scrub_payload(payload.model_dump())
    
    if hasattr(payload, "__dict__"):
        return scrub_payload(payload.__dict__)

    return payload


from sqlalchemy.orm import Session


def write_to_dlq(
    target_service: str,
    operation: str,
    payload: Any,
    attempts: int,
    error: str,
    organization_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Optional[str]:
    """
    Persist an exhausted external call into failed_external_calls table.
    Scrubs sensitive fields and caps payload length to DLQ_PAYLOAD_MAX_BYTES.
    Never raises an exception so caller flow is never interrupted.
    """
    try:
        scrubbed = scrub_payload(payload)
        try:
            payload_str = json.dumps(scrubbed, default=str)
        except Exception:
            payload_str = str(scrubbed)

        max_bytes = getattr(settings, "DLQ_PAYLOAD_MAX_BYTES", 10000)
        if len(payload_str) > max_bytes:
            payload_str = payload_str[:max_bytes] + "... [TRUNCATED]"

        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            failed_call = FailedExternalCall(
                target_service=target_service,
                operation=operation,
                organization_id=organization_id,
                scan_id=scan_id,
                payload=payload_str,
                attempts=attempts,
                last_error=str(error),
                status="FAILED",
                created_at=datetime.now(timezone.utc)
            )
            db.add(failed_call)
            db.commit()
            db.refresh(failed_call)
            logger.warning(
                f"Recorded failed external call in DLQ (id={failed_call.id}, target={target_service}, op={operation})"
            )
            return failed_call.id
        finally:
            if close_db:
                db.close()
    except Exception as exc:
        logger.error(f"Failed to record call in DLQ: {exc}", exc_info=True)
        return None
