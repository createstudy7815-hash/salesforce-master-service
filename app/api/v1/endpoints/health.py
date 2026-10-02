import time
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings
from app.schemas.common import HealthResponse, ServiceStatsResponse
from app.models.job import Job, JobStatus

router = APIRouter()
START_TIME = time.time()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Liveness and readiness health check probe."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # Check MinIO reachability lightly
    minio_ok = True
    try:
        import socket
        host, port = settings.MINIO_ENDPOINT.split(":")
        s = socket.create_connection((host, int(port)), timeout=2.0)
        s.close()
    except Exception:
        minio_ok = False

    overall_status = "ok" if (db_ok and minio_ok) else "degraded"

    return HealthResponse(
        status=overall_status,
        database_connected=db_ok,
        minio_connected=minio_ok,
        version="0.1.0",
        environment=settings.APP_ENV
    )


@router.get("/stats", response_model=ServiceStatsResponse, tags=["Health"])
def service_stats(db: Session = Depends(get_db)):
    """Lightweight service-level job counters."""
    uptime = time.time() - START_TIME
    try:
        total = db.query(Job).count()
        active = db.query(Job).filter(Job.status.notin_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])).count()
        completed = db.query(Job).filter(Job.status == JobStatus.COMPLETED).count()
        failed = db.query(Job).filter(Job.status == JobStatus.FAILED).count()
    except Exception:
        total, active, completed, failed = 0, 0, 0, 0

    return ServiceStatsResponse(
        total_jobs=total,
        active_jobs=active,
        completed_jobs=completed,
        failed_jobs=failed,
        uptime_seconds=round(uptime, 2)
    )
