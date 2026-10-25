from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.hmac_auth import hmac_auth_required, HMACClient
from app.schemas.normalization import (
    NormalizeScanRequest,
    NormalizeScanResponse,
    NormalizeObjectResponse,
    NormalizedTablesListResponse,
    NormalizedTableItem,
    SupportedObjectsResponse
)
from app.services.normalization_service import normalization_service

router = APIRouter()


@router.post(
    "/{scan_id}/normalize",
    response_model=NormalizeScanResponse,
    summary="Normalize extracted datasets into tabular tables"
)
async def normalize_scan(
    scan_id: str,
    request: Optional[NormalizeScanRequest] = None,
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Transforms extracted CSVs for a scan into clean, flat relational tables.
    Saves tables as Parquet or JSON, and optionally publishes to MinIO.
    """
    req = request or NormalizeScanRequest()
    try:
        result = await normalization_service.normalize_scan(
            scan_id=scan_id,
            format=req.format,
            save_to_disk=req.save_to_disk,
            upload_to_minio=req.upload_to_minio,
            processing_date=req.processing_date,
            db=db
        )
        return NormalizeScanResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Normalization execution failed: {exc}"
        )


@router.post(
    "/{scan_id}/normalize/{object_name}",
    response_model=NormalizeObjectResponse,
    summary="Normalize a single extracted Salesforce object"
)
async def normalize_single_object(
    scan_id: str,
    object_name: str,
    format: str = Query("parquet", description="Output format: 'parquet' or 'json'"),
    save_to_disk: bool = Query(True, description="Persist normalized table to disk"),
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Normalizes a single Salesforce object (e.g. Account, Contact, Opportunity) from extracted files.
    """
    try:
        result = await normalization_service.normalize_single_object(
            scan_id=scan_id,
            object_name=object_name,
            format=format,
            save_to_disk=save_to_disk,
            db=db
        )
        return NormalizeObjectResponse(**result)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Single object normalization failed: {exc}"
        )


@router.get(
    "/{scan_id}/tables",
    response_model=NormalizedTablesListResponse,
    summary="List normalized table files for a scan"
)
def list_normalized_tables(
    scan_id: str,
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Lists all normalized table files on disk for the given scan with record counts and file sizes.
    """
    tables_meta = normalization_service.list_normalized_tables(scan_id)
    items = [NormalizedTableItem(**tbl) for tbl in tables_meta]
    return NormalizedTablesListResponse(
        scan_id=scan_id,
        total_tables=len(items),
        tables=items
    )


@router.get(
    "/supported-objects",
    response_model=SupportedObjectsResponse,
    summary="Catalog of supported Salesforce objects and output tables"
)
def get_supported_objects(
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Returns the static catalog of supported Salesforce objects and target relational tables.
    """
    catalog = normalization_service.get_supported_objects()
    return SupportedObjectsResponse(supported_objects=catalog)
