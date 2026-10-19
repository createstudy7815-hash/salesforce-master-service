import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import SessionLocal
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def write_audit(
        event_category: str,
        event_type: str,
        organization_id: Optional[str] = None,
        outcome: str = "SUCCESS",
        actor_client_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        entity_type: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        http_method: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_ip: Optional[str] = None,
        status_code: Optional[int] = None,
        severity: str = "INFO",
        error_detail: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Optional[str]:
        """
        Record an audit log entry.
        Never raises an exception so request paths are never disrupted.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            entry = AuditLog(
                event_category=event_category,
                event_type=event_type,
                organization_id=organization_id,
                outcome=outcome,
                actor_client_id=actor_client_id,
                actor_role=actor_role,
                entity_type=entity_type,
                resource_type=resource_type,
                resource_id=resource_id,
                http_method=http_method,
                endpoint=endpoint,
                request_ip=request_ip,
                status_code=status_code,
                severity=severity,
                error_detail=error_detail,
                extra_metadata=extra_metadata,
                created_at=datetime.now(timezone.utc)
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return entry.id
        except Exception as exc:
            logger.error(f"Failed to record audit log: {exc}", exc_info=True)
            return None
        finally:
            if close_db:
                db.close()

    @staticmethod
    def get_audit_logs(
        db: Session,
        organization_id: Optional[str] = None,
        event_category: Optional[str] = None,
        event_type: Optional[str] = None,
        outcome: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[AuditLog], int]:
        """Query audit logs with pagination and filters."""
        query = db.query(AuditLog)

        if organization_id:
            query = query.filter(AuditLog.organization_id == organization_id)
        if event_category:
            query = query.filter(AuditLog.event_category == event_category)
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        if outcome:
            query = query.filter(AuditLog.outcome == outcome)
        if from_date:
            query = query.filter(AuditLog.created_at >= from_date)
        if to_date:
            query = query.filter(AuditLog.created_at <= to_date)

        total = query.count()
        offset = (page - 1) * page_size
        items = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(page_size).all()
        return items, total

    @staticmethod
    def get_audit_stats(db: Session, window_minutes: int = 60) -> Dict[str, Any]:
        """Compute rolling-window audit aggregations."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        query = db.query(AuditLog).filter(AuditLog.created_at >= cutoff)

        total_events = query.count()

        # Breakdown by outcome
        outcomes = dict(
            db.query(AuditLog.outcome, func.count(AuditLog.id))
            .filter(AuditLog.created_at >= cutoff)
            .group_by(AuditLog.outcome)
            .all()
        )

        # Breakdown by category
        categories = dict(
            db.query(AuditLog.event_category, func.count(AuditLog.id))
            .filter(AuditLog.created_at >= cutoff)
            .group_by(AuditLog.event_category)
            .all()
        )

        return {
            "window_minutes": window_minutes,
            "total_events": total_events,
            "by_outcome": outcomes,
            "by_category": categories
        }


audit_service = AuditService()
