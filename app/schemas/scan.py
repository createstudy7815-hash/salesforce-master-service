from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.job import JobStatus
from app.schemas.auth import SalesforceCredentials


class ScanStartRequest(BaseModel):
    organization_id: str = Field(..., description="Unique Salesforce Organization ID")
    credentials: SalesforceCredentials = Field(..., description="Salesforce login credentials")
    objects: Optional[List[str]] = Field(
        None,
        description="List of Salesforce objects to export. Defaults to all supported objects."
    )
    soql_queries: Optional[Dict[str, str]] = Field(
        None,
        description="Optional custom SOQL query per object (e.g. {'Account': 'SELECT Id, Name FROM Account'})"
    )
    auto_normalize: Optional[bool] = Field(
        False,
        description="Whether to automatically run normalization after extraction completes"
    )
    upload_to_minio: Optional[bool] = Field(
        False,
        description="Whether to automatically upload normalized tables to MinIO"
    )
    output_format: Optional[str] = Field(
        "parquet",
        description="Format for normalized tables: 'parquet' or 'json'"
    )
    processing_date: Optional[str] = Field(
        None,
        description="Optional processing date for MinIO partitioning (YYYY-MM-DD)"
    )


class ScanStartResponse(BaseModel):
    scan_id: str
    organization_id: str
    status: JobStatus
    message: str
    created_at: datetime


class ScanStatusResponse(BaseModel):
    scan_id: str
    organization_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    last_heartbeat: datetime
    batch_status: Optional[str] = None
    batch_job_ids: Optional[Dict[str, str]] = None
    file_paths: Optional[List[str]] = None
    file_sizes: Optional[Dict[str, int]] = None
    entity_record_counts: Optional[Dict[str, int]] = None
    normalized_at: Optional[datetime] = None
    normalization_stats: Optional[Dict[str, Any]] = None
    minio_uploaded_at: Optional[datetime] = None
    minio_object_keys: Optional[List[str]] = None
    pipeline_progress: Dict[str, Any]
    error_message: Optional[str] = None


class ScanItem(BaseModel):
    scan_id: str
    organization_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    last_heartbeat: datetime
    error_message: Optional[str] = None


class ScanListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[ScanItem]


class ScanStatisticsResponse(BaseModel):
    total_scans: int
    by_status: Dict[str, int]
