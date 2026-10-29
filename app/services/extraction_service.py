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
from app.services.minio_client import minio_client

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Top-level orchestrator for Salesforce extraction runs:
    - Accepts new scan requests, responds immediately (202 Accepted)
    - Executes background pipeline (Submit -> Poll -> Download -> Extract -> Normalize -> MinIO Upload)
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
            auto_normalize=request.auto_normalize or request.upload_to_minio,
            upload_to_minio=request.upload_to_minio,
            output_format=request.output_format or "parquet",
            processing_date=request.processing_date,
            db=db
        )

        logger.info(
            f"Scan {scan_id} initiated for org {request.organization_id} "
            f"with {len(objects)} objects (auto_normalize={request.auto_normalize}, "
            f"upload_to_minio={request.upload_to_minio})."
        )
        return job

    async def _execute_batch_workflow(
        self,
        scan_id: str,
        creds: SalesforceCredentials,
        objects: List[str],
        soql_queries: Optional[Dict[str, str]] = None,
        auto_normalize: bool = False,
        upload_to_minio: bool = False,
        output_format: str = "parquet",
        processing_date: Optional[str] = None,
        db: Optional[Any] = None
    ) -> None:
        """
        Asynchronous background pipeline:
        1. Submit Bulk API 2.0 query jobs per object
        2. Poll until all jobs are JobComplete
        3. Download CSV results to data/scans/{scan_id}/extracted/
        4. Inspect extracted records and update entity_record_counts -> EXTRACTED
        5. (Optional) Run normalization into Parquet/JSON -> NORMALIZED
        6. (Optional) Upload normalized tables to MinIO -> UPLOADING_TO_MINIO -> COMPLETED
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

            # 5. Normalization & MinIO upload (if requested)
            if auto_normalize or upload_to_minio:
                from app.services.normalization_service import normalization_service
                logger.info(
                    f"Auto-normalizing scan {scan_id} (format={output_format}, "
                    f"upload_to_minio={upload_to_minio})..."
                )
                await normalization_service.normalize_scan(
                    scan_id=scan_id,
                    format=output_format,
                    save_to_disk=True,
                    upload_to_minio=upload_to_minio,
                    processing_date=processing_date,
                    db=db
                )

        except Exception as exc:
            logger.error(f"Scan {scan_id} failed during workflow execution: {exc}", exc_info=True)
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

        if job.status == JobStatus.COMPLETED:
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
        """
        Resume pipeline from the last completed stage:
        (download -> extraction -> normalization -> MinIO upload)
        """
        job = job_service.get_job(scan_id, db=db)
        if not job:
            return

        try:
            # Case 1: Interrupted or failed during MinIO upload
            if job.status in (JobStatus.UPLOADING_TO_MINIO, JobStatus.UPLOADED_TO_MINIO) or (
                job.normalized_at and not job.minio_uploaded_at and job.status in (JobStatus.FAILED, JobStatus.CANCELLED)
            ):
                logger.info(f"Resuming scan {scan_id} from MinIO upload stage...")
                job_service.start_minio_upload(scan_id, db=db)
                table_stats = job.normalization_stats.get("table_stats") if job.normalization_stats else None
                uploaded_keys = minio_client.upload_normalized_data(
                    scan_id=scan_id,
                    organization_id=job.organization_id,
                    processing_date=None,
                    tables=table_stats
                )
                job_service.complete_minio_upload(
                    scan_id=scan_id,
                    minio_object_keys=uploaded_keys,
                    mark_completed=True,
                    db=db
                )
                logger.info(f"Scan {scan_id} resumed and successfully published to MinIO.")
                return

            # Case 2: Interrupted or failed during normalization
            if job.status == JobStatus.NORMALIZING or (
                job.extracted_at and not job.normalized_at and job.status in (JobStatus.FAILED, JobStatus.CANCELLED)
            ):
                logger.info(f"Resuming scan {scan_id} from normalization stage...")
                from app.services.normalization_service import normalization_service
                await normalization_service.normalize_scan(
                    scan_id=scan_id,
                    format="parquet",
                    save_to_disk=True,
                    upload_to_minio=bool(job.minio_object_keys or job.minio_uploaded_at),
                    db=db
                )
                logger.info(f"Scan {scan_id} resumed and normalization completed.")
                return

            # Case 3: Need to resume batch query / download / extract
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
            if not job.extracted_at:
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
