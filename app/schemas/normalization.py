from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class NormalizeScanRequest(BaseModel):
    format: str = Field("parquet", description="Output serialization format: 'parquet' or 'json'")
    save_to_disk: bool = Field(True, description="Persist normalized tables to local disk")
    upload_to_minio: bool = Field(False, description="Publish normalized tables to MinIO storage")
    processing_date: Optional[str] = Field(None, description="Partition date in YYYY-MM-DD format (defaults to current date)")


class NormalizeScanResponse(BaseModel):
    scan_id: str
    format: str
    total_tables: int
    total_records: int
    tables_generated: List[str]
    table_stats: Dict[str, Any]
    normalized_at: str
    minio_uploaded: Optional[bool] = False
    minio_object_keys: Optional[List[str]] = None


class NormalizeObjectResponse(BaseModel):
    scan_id: str
    object_name: str
    format: str
    total_tables: int
    total_records: int
    tables_generated: List[str]
    table_stats: Dict[str, Any]


class NormalizedTableItem(BaseModel):
    table_name: str
    file_name: str
    format: str
    size_bytes: int
    record_count: int
    file_path: str


class NormalizedTablesListResponse(BaseModel):
    scan_id: str
    total_tables: int
    tables: List[NormalizedTableItem]


class SupportedObjectCatalogItem(BaseModel):
    object_name: str
    target_tables: List[str]
    description: str


class SupportedObjectsResponse(BaseModel):
    supported_objects: List[SupportedObjectCatalogItem]
