import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_category = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor_client_id = Column(String(64), nullable=True)
    actor_role = Column(String(32), nullable=True)
    organization_id = Column(String(64), nullable=True, index=True)
    entity_type = Column(String(64), nullable=True)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(64), nullable=True)
    http_method = Column(String(16), nullable=True)
    endpoint = Column(String(255), nullable=True)
    request_ip = Column(String(64), nullable=True)
    status_code = Column(Integer, nullable=True)
    outcome = Column(String(32), nullable=False)  # SUCCESS, FAILURE, ERROR, DENIED
    severity = Column(String(16), default="INFO")
    error_detail = Column(Text, nullable=True)
    extra_metadata = Column(JSON, default=dict, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
