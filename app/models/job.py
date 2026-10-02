import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Text, Enum as SQLEnum
from app.core.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    BATCH_REQUESTED = "BATCH_REQUESTED"
    BATCH_PROCESSING = "BATCH_PROCESSING"
    BATCH_READY = "BATCH_READY"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    NORMALIZING = "NORMALIZING"
    NORMALIZED = "NORMALIZED"
    UPLOADING_TO_MINIO = "UPLOADING_TO_MINIO"
    UPLOADED_TO_MINIO = "UPLOADED_TO_MINIO"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True, index=True)
    organization_id = Column(String(64), index=True, nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_heartbeat = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Batch (Bulk API 2.0)
    batch_requested_at = Column(DateTime(timezone=True), nullable=True)
    batch_job_ids = Column(JSON, default=dict, nullable=True)  # { "Account": "750...", "Contact": "750..." }
    batch_status = Column(String(64), nullable=True)

    # Download
    downloaded_at = Column(DateTime(timezone=True), nullable=True)
    file_paths = Column(JSON, default=list, nullable=True)
    file_sizes = Column(JSON, default=dict, nullable=True)

    # Extraction
    extracted_at = Column(DateTime(timezone=True), nullable=True)
    entity_record_counts = Column(JSON, default=dict, nullable=True)

    # Normalization
    normalized_at = Column(DateTime(timezone=True), nullable=True)
    normalization_stats = Column(JSON, default=dict, nullable=True)

    # MinIO
    minio_uploaded_at = Column(DateTime(timezone=True), nullable=True)
    minio_object_keys = Column(JSON, default=list, nullable=True)

    # Error details
    error_message = Column(Text, nullable=True)
