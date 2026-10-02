import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FailedExternalCall(Base):
    __tablename__ = "failed_external_calls"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_service = Column(String(64), nullable=False, index=True)  # "salesforce", "minio"
    operation = Column(String(64), nullable=False)
    organization_id = Column(String(64), nullable=True, index=True)
    scan_id = Column(String(64), nullable=True, index=True)
    payload = Column(JSON, nullable=True)  # scrubbed and capped payload
    attempts = Column(Integer, default=1, nullable=False)
    last_error = Column(Text, nullable=True)
    status = Column(String(32), default="FAILED", nullable=False)  # "FAILED", "REPLAYED", "DISCARDED"
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
