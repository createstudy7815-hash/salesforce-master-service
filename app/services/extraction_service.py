import uuid
import logging
from typing import Dict, List, Optional, Any
from fastapi import BackgroundTasks

from app.core.config import settings
from app.models.job import Job, JobStatus
from app.schemas.auth import SalesforceCredentials
from app.schemas.scan import ScanStartRequest
from app.services.job_service import job_service
from app.services.batch_file_service import batch_file_service
from app.services.batch_polling_service import batch_polling_service
from app.services.sf_batch_client import sf_batch_client

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Top-level orchestrator for Salesforce extraction runs:
    - Accepts new scan requests, responds immediately (202 Accepted)
    - Executes background extraction pipeline (Submit -> Poll -> Download -> Extract)
    - Resumes failed/cancelled scans from the last completed stage
    - Cancels running scans locally and remotely
    """
    def __init__(self):
        self.default_objects = settings.SF_SUPPORTED_OBJECTS

    async def start_scan(
        self,
        request: ScanStartRequest,
        background_tasks: BackgroundTasks,
        db: Optional[Any] = None
    ) -> Job:
        """
        Validate payload, create job record in DB, and launch background extraction workflow.
        Returns immediately with PENDING Job row.
        """
        scan_id = f"scan_{uuid.uuid4().hex[:12]}"
        objects = request.objects or self.default_objects

        job = job_service.create_job(
            scan_id=scan_id,
            organization_id=request.organization_id,
            db=db
        )

        background_tasks.add_task(
            self._execute_batch_workflow,
            scan_id=scan_id,
            creds=request.credentials,
            objects=objects,
            soql_queries=request.soql_queries,
            db=db
        )

        logger.info(f"Scan {scan_id} initiated for org {request.organization_id} with {len(objects)} objects.")
        return job

    async def _execute_batch_workflow(
        self,
        scan_id: str,
        creds: SalesforceCredentials,
        objects: List[str],
        soql_queries: Optional[Dict[str, str]] = None,
        db: Optional[Any] = None
    ) -> None:
        """
        Asynchronous background pipeline:
        1. Submit Bulk API 2.0 query jobs per object
        2. Poll until all jobs are JobComplete
        3. Download CSV results to data/scans/{scan_id}/extracted/
        4. Inspect extracted records and update entity_record_counts -> EXTRACTED
        """
        try:
            # 1. Submit
            await batch_polling_service.submit_batch_jobs(
                scan_id=scan_id,
                objects=objects,
                creds=creds,
                soql_queries=soql_queries
            )

            # 2. Poll
            poll_result = await batch_polling_service.poll_until_ready(
                scan_id=scan_id,
                creds=creds
            )
            if poll_result.get("status") == "CANCELLED":
                return

            # 3. Download
            await batch_polling_service.download_results(
                scan_id=scan_id,
                creds=creds
            )

            # 4. Extract / parse row counts
            job_service.update_job_status(scan_id, JobStatus.EXTRACTING, db=db)
            file_info = batch_file_service.get_file_info(scan_id)
            
            job_service.update_extraction_info(
                scan_id=scan_id,
                entity_record_counts=file_info["record_counts"],
                db=db
            )
            logger.info(f"Scan {scan_id} successfully reached status EXTRACTED: {file_info['record_counts']}")

        except Exception as exc:
            logger.error(f"Scan {scan_id} failed during batch extraction: {exc}", exc_info=True)
            job_service.fail_job(scan_id, error=str(exc), db=db)

    async def resume_scan(
        self,
        scan_id: str,
        creds: SalesforceCredentials,
        background_tasks: BackgroundTasks,
        db: Optional[Any] = None
    ) -> Job:
        """
        Resume a failed or cancelled scan from its last completed stage.
        """
        job = job_service.get_job(scan_id, db=db)
        if not job:
            raise ValueError(f"Scan {scan_id} not found.")

        if job.status in (JobStatus.COMPLETED, JobStatus.EXTRACTED, JobStatus.NORMALIZED):
            return job

        # Launch resumption in background
        background_tasks.add_task(
            self._execute_resume_workflow,
            scan_id=scan_id,
            creds=creds,
            db=db
        )
        return job

    async def _execute_resume_workflow(
        self,
        scan_id: str,
        creds: SalesforceCredentials,
        db: Optional[Any] = None
    ) -> None:
        """Resume pipeline from stage corresponding to current job state."""
        job = job_service.get_job(scan_id, db=db)
        if not job:
            return

        try:
            # If batch jobs were never submitted, restart from scratch
            if not job.batch_job_ids:
                await self._execute_batch_workflow(
                    scan_id=scan_id,
                    creds=creds,
                    objects=self.default_objects,
                    db=db
                )
                return

            # If not yet batch ready, poll again
            if not job.downloaded_at:
                if job.status != JobStatus.BATCH_READY:
                    await batch_polling_service.poll_until_ready(scan_id=scan_id, creds=creds)
                await batch_polling_service.download_results(scan_id=scan_id, creds=creds)

            # Parse files
            job_service.update_job_status(scan_id, JobStatus.EXTRACTING, db=db)
            file_info = batch_file_service.get_file_info(scan_id)
            job_service.update_extraction_info(
                scan_id=scan_id,
                entity_record_counts=file_info["record_counts"],
                db=db
            )
            logger.info(f"Scan {scan_id} resumed and reached EXTRACTED.")
        except Exception as exc:
            logger.error(f"Scan {scan_id} resumption failed: {exc}", exc_info=True)
            job_service.fail_job(scan_id, error=str(exc), db=db)

    async def cancel_scan(
        self,
        scan_id: str,
        creds: Optional[SalesforceCredentials] = None,
        db: Optional[Any] = None
    ) -> Job:
        """
        Cancel scan locally and attempt best-effort abort of remote Bulk API jobs.
        """
        job = job_service.get_job(scan_id, db=db)
        if not job:
            raise ValueError(f"Scan {scan_id} not found.")

        # Local cancel
        job_service.cancel_job(scan_id, db=db)

        # Remote abort if credentials available and batch jobs submitted
        if creds and job.batch_job_ids:
            for obj_name, remote_job_id in job.batch_job_ids.items():
                try:
                    await sf_batch_client.abort_job(remote_job_id, creds)
                except Exception as exc:
                    logger.warning(f"Could not abort remote job {remote_job_id}: {exc}")

        return job_service.get_job(scan_id, db=db)

    def remove_scan(self, scan_id: str, db: Optional[Any] = None) -> bool:
        """
        Delete scan record from DB and clean up extracted files on disk.
        """
        # BatchFileService cleanup
        batch_file_service.cleanup_extracted_files(scan_id)
        # DB row delete
        return job_service.remove_job(scan_id, db=db)


extraction_service = ExtractionService()
