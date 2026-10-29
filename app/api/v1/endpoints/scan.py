from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.hmac_auth import hmac_auth_required, HMACClient
from app.models.job import JobStatus
from app.schemas.auth import SalesforceCredentials
from app.schemas.scan import (
    ScanStartRequest,
    ScanStartResponse,
    ScanStatusResponse,
    ScanListResponse,
    ScanItem,
    ScanStatisticsResponse
)
from app.services.job_service import job_service
from app.services.extraction_service import extraction_service

router = APIRouter()


@router.post(
    "/start",
    response_model=ScanStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new Salesforce extraction scan"
)
async def start_scan(
    request: ScanStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Validates payload, creates tracking job, kicks off background extraction workflow,
    and returns 202 Accepted immediately.
    """
    job = await extraction_service.start_scan(request, background_tasks, db=db)
    return ScanStartResponse(
        scan_id=job.id,
        organization_id=job.organization_id,
        status=job.status,
        message="Scan initiated and running in background.",
        created_at=job.created_at
    )


@router.get(
    "/{scan_id}/status",
    response_model=ScanStatusResponse,
    summary="Check the status and pipeline progress of a scan"
)
def get_scan_status(
    scan_id: str,
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Returns current job status, pipeline stage timestamps, and extracted entity record counts.
    """
    job = job_service.get_job(scan_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan with ID '{scan_id}' not found."
        )

    pipeline_progress = job_service.get_pipeline_progress(job)

    return ScanStatusResponse(
        scan_id=job.id,
        organization_id=job.organization_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        last_heartbeat=job.last_heartbeat,
        batch_status=job.batch_status,
        batch_job_ids=job.batch_job_ids,
        file_paths=job.file_paths,
        file_sizes=job.file_sizes,
        entity_record_counts=job.entity_record_counts,
        normalized_at=job.normalized_at,
        normalization_stats=job.normalization_stats,
        minio_uploaded_at=job.minio_uploaded_at,
        minio_object_keys=job.minio_object_keys,
        pipeline_progress=pipeline_progress,
        error_message=job.error_message
    )


@router.post(
    "/{scan_id}/cancel",
    summary="Cancel an active scan"
)
async def cancel_scan(
    scan_id: str,
    creds: Optional[SalesforceCredentials] = None,
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Cancels the scan locally and attempts remote Bulk API cancellation.
    """
    try:
        job = await extraction_service.cancel_scan(scan_id, creds=creds, db=db)
        return {
            "scan_id": job.id,
            "status": job.status,
            "message": "Scan cancelled successfully."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{scan_id}/resume",
    summary="Resume a failed or cancelled scan"
)
async def resume_scan(
    scan_id: str,
    creds: SalesforceCredentials,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Resumes a failed or cancelled scan from the last completed pipeline stage.
    """
    try:
        job = await extraction_service.resume_scan(scan_id, creds, background_tasks, db=db)
        return {
            "scan_id": job.id,
            "status": job.status,
            "message": "Scan resumption launched in background."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/list",
    response_model=ScanListResponse,
    summary="List past and active scans"
)
def list_scans(
    organization_id: Optional[str] = Query(None, description="Filter by Organization ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Returns a paginated list of scans.
    """
    jobs, total = job_service.list_jobs(
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        db=db
    )
    return ScanListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[
            ScanItem(
                scan_id=j.id,
                organization_id=j.organization_id,
                status=j.status,
                created_at=j.created_at,
                updated_at=j.updated_at,
                last_heartbeat=j.last_heartbeat,
                error_message=j.error_message
            )
            for j in jobs
        ]
    )


@router.get(
    "/statistics",
    response_model=ScanStatisticsResponse,
    summary="Get aggregate scan statistics by status"
)
def get_scan_statistics(
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Aggregate counts of scans categorized by status.
    """
    stats = job_service.get_scan_statistics(db=db)
    return ScanStatisticsResponse(
        total_scans=stats["total_scans"],
        by_status=stats["by_status"]
    )


@router.delete(
    "/{scan_id}/remove",
    summary="Delete a scan record and its local files"
)
def remove_scan(
    scan_id: str,
    db: Session = Depends(get_db),
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Deletes job record and cleans up extracted files. Blocked while scan is actively running.
    """
    try:
        success = extraction_service.remove_scan(scan_id, db=db)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan '{scan_id}' not found."
            )
        return {
            "scan_id": scan_id,
            "status": "DELETED",
            "message": "Scan and local extracted files successfully deleted."
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
