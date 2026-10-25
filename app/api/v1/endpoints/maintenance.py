from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.hmac_auth import hmac_auth_required, HMACClient
from app.services.job_service import job_service

router = APIRouter()


@router.post(
    "/cleanup",
    summary="Delete old scans and local files older than N days"
)
def cleanup_old_scans(
    days_old: int = Query(30, ge=1, description="Number of days threshold for scan retention"),
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
) -> Dict[str, Any]:
    """
    Deletes scan records and associated local storage files for scans older than N days.
    """
    deleted_ids = job_service.cleanup_old_jobs(days_old=days_old, db=db)
    return {
        "status": "success",
        "days_threshold": days_old,
        "deleted_count": len(deleted_ids),
        "deleted_scan_ids": deleted_ids
    }


@router.post(
    "/detect-crashed",
    summary="Detect and flag jobs with stale heartbeats as FAILED"
)
def detect_crashed_jobs(
    timeout_minutes: int = Query(15, ge=1, description="Heartbeat inactivity timeout in minutes"),
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
) -> Dict[str, Any]:
    """
    Scans active in-progress jobs and marks any with stale heartbeats as FAILED.
    """
    crashed_ids = job_service.detect_crashed_jobs(timeout_minutes=timeout_minutes, db=db)
    return {
        "status": "success",
        "timeout_minutes": timeout_minutes,
        "crashed_count": len(crashed_ids),
        "crashed_job_ids": crashed_ids
    }
