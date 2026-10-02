from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    database_connected: bool
    minio_connected: bool
    version: str = "0.1.0"
    environment: str = "development"


class ServiceStatsResponse(BaseModel):
    total_jobs: int = 0
    active_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    uptime_seconds: Optional[float] = None
    extra_counters: Dict[str, Any] = Field(default_factory=dict)
