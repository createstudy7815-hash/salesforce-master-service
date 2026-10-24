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
