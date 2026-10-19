from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.hmac_auth import hmac_auth_required, HMACClient
from app.services.audit import audit_service

router = APIRouter()


@router.get("/logs", tags=["Audit"])
def get_audit_logs(
    organization_id: Optional[str] = Query(None, description="Filter by Organization ID"),
    event_category: Optional[str] = Query(None, description="Filter by Event Category"),
    event_type: Optional[str] = Query(None, description="Filter by Event Type"),
    outcome: Optional[str] = Query(None, description="Filter by Outcome (SUCCESS/FAILURE/DENIED)"),
    from_date: Optional[datetime] = Query(None, description="Start datetime ISO format"),
    to_date: Optional[datetime] = Query(None, description="End datetime ISO format"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Paginated audit log query. Requires HMAC authentication.
    """
    items, total = audit_service.get_audit_logs(
        db=db,
        organization_id=organization_id,
        event_category=event_category,
        event_type=event_type,
        outcome=outcome,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size
    )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [
            {
                "id": log.id,
                "event_category": log.event_category,
                "event_type": log.event_type,
                "actor_client_id": log.actor_client_id,
                "actor_role": log.actor_role,
                "organization_id": log.organization_id,
                "endpoint": log.endpoint,
                "http_method": log.http_method,
                "status_code": log.status_code,
                "outcome": log.outcome,
                "severity": log.severity,
                "error_detail": log.error_detail,
                "extra_metadata": log.extra_metadata,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in items
        ]
    }


@router.get("/stats", tags=["Audit"])
def get_audit_stats(
    window_minutes: int = Query(60, ge=1, le=1440, description="Rolling time window in minutes"),
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Rolling-window audit aggregates. Requires HMAC authentication.
    """
    return audit_service.get_audit_stats(db=db, window_minutes=window_minutes)
