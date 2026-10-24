import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import SessionLocal
from app.models.job import Job, JobStatus, utc_now

logger = logging.getLogger(__name__)


class JobService:
    @staticmethod
    def create_job(
        scan_id: str,
        organization_id: str,
        db: Optional[Session] = None
    ) -> Job:
        """Create and initialize a Job row with status PENDING."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            now = utc_now()
            job = Job(
                id=scan_id,
                organization_id=organization_id,
                status=JobStatus.PENDING,
                created_at=now,
                updated_at=now,
                last_heartbeat=now,
                batch_job_ids={},
                file_paths=[],
                file_sizes={},
                entity_record_counts={},
                normalization_stats={},
                minio_object_keys=[]
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job
        finally:
            if close_db:
                db.close()

    @staticmethod
    def get_job(scan_id: str, db: Optional[Session] = None) -> Optional[Job]:
        """Fetch a Job by its scan_id."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            return db.query(Job).filter(Job.id == scan_id).first()
        finally:
            if close_db:
                db.close()

    @staticmethod
    def update_job_status(
        scan_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Update job status and refresh last_heartbeat and updated_at."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            job = db.query(Job).filter(Job.id == scan_id).first()
            if job:
                job.status = status
                job.updated_at = utc_now()
                job.last_heartbeat = utc_now()
                if error_message:
                    job.error_message = str(error_message)
                db.commit()
                db.refresh(job)
            return job
        finally:
            if close_db:
                db.close()

    @staticmethod
    def update_heartbeat(scan_id: str, db: Optional[Session] = None) -> None:
        """Refresh last_heartbeat timestamp for active scan."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            job = db.query(Job).filter(Job.id == scan_id).first()
            if job:
                job.last_heartbeat = utc_now()
                db.commit()
        finally:
            if close_db:
                db.close()

    @staticmethod
    def update_batch_info(
        scan_id: str,
        batch_job_ids: Dict[str, str],
        batch_status: str,
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Record Bulk API job IDs per object."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            job = db.query(Job).filter(Job.id == scan_id).first()
            if job:
                job.batch_job_ids = batch_job_ids
                job.batch_status = batch_status
                job.batch_requested_at = utc_now()
                job.status = JobStatus.BATCH_REQUESTED
                job.updated_at = utc_now()
                job.last_heartbeat = utc_now()
                db.commit()
                db.refresh(job)
            return job
        finally:
            if close_db:
                db.close()

    @staticmethod
    def update_download_info(
        scan_id: str,
        file_paths: List[str],
        file_sizes: Dict[str, int],
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Record downloaded CSV paths and sizes."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            job = db.query(Job).filter(Job.id == scan_id).first()
            if job:
                job.file_paths = file_paths
                job.file_sizes = file_sizes
                job.downloaded_at = utc_now()
                job.status = JobStatus.DOWNLOADED
                job.updated_at = utc_now()
                job.last_heartbeat = utc_now()
                db.commit()
                db.refresh(job)
            return job
        finally:
            if close_db:
                db.close()

    @staticmethod
    def update_extraction_info(
        scan_id: str,
        entity_record_counts: Dict[str, int],
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Record parsed record counts per entity."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            job = db.query(Job).filter(Job.id == scan_id).first()
            if job:
                job.entity_record_counts = entity_record_counts
                job.extracted_at = utc_now()
                job.status = JobStatus.EXTRACTED
                job.updated_at = utc_now()
                job.last_heartbeat = utc_now()
                db.commit()
                db.refresh(job)
            return job
        finally:
            if close_db:
                db.close()

    @staticmethod
    def fail_job(scan_id: str, error: str, db: Optional[Session] = None) -> Optional[Job]:
        """Mark job as FAILED with error message."""
        return JobService.update_job_status(scan_id, JobStatus.FAILED, error_message=error, db=db)

    @staticmethod
    def cancel_job(scan_id: str, db: Optional[Session] = None) -> Optional[Job]:
        """Mark job as CANCELLED."""
        return JobService.update_job_status(scan_id, JobStatus.CANCELLED, db=db)

    @staticmethod
    def get_pipeline_progress(job: Job) -> Dict[str, Any]:
        """Build structured stage execution status."""
        stages = [
            ("batch_requested", job.batch_requested_at is not None),
            ("downloaded", job.downloaded_at is not None),
            ("extracted", job.extracted_at is not None),
            ("normalized", job.normalized_at is not None),
            ("minio_uploaded", job.minio_uploaded_at is not None),
            ("completed", job.status == JobStatus.COMPLETED)
        ]
        return {
            "current_status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "stages": {name: done for name, done in stages},
            "timestamps": {
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "batch_requested_at": job.batch_requested_at.isoformat() if job.batch_requested_at else None,
                "downloaded_at": job.downloaded_at.isoformat() if job.downloaded_at else None,
                "extracted_at": job.extracted_at.isoformat() if job.extracted_at else None,
                "normalized_at": job.normalized_at.isoformat() if job.normalized_at else None,
                "minio_uploaded_at": job.minio_uploaded_at.isoformat() if job.minio_uploaded_at else None,
            }
        }

    @staticmethod
    def list_jobs(
        organization_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        db: Optional[Session] = None
    ) -> Tuple[List[Job], int]:
        """Paginated list of scans."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            query = db.query(Job)
            if organization_id:
                query = query.filter(Job.organization_id == organization_id)
            total = query.count()
            offset = (page - 1) * page_size
            items = query.order_by(desc(Job.created_at)).offset(offset).limit(page_size).all()
            return items, total
        finally:
            if close_db:
                db.close()

    @staticmethod
    def get_scan_statistics(db: Optional[Session] = None) -> Dict[str, Any]:
        """Return aggregate job counts by status."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            counts = dict(db.query(Job.status, func.count(Job.id)).group_by(Job.status).all())
            total = sum(counts.values())
            # Format status keys as strings
            by_status = {
                (k.value if hasattr(k, "value") else str(k)): v
                for k, v in counts.items()
            }
            return {
                "total_scans": total,
                "by_status": by_status
            }
        finally:
            if close_db:
                db.close()

    @staticmethod
    def remove_job(scan_id: str, db: Optional[Session] = None) -> bool:
        """Delete job from DB (fails if actively in progress)."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            job = db.query(Job).filter(Job.id == scan_id).first()
            if not job:
                return False
            active_statuses = [
                JobStatus.BATCH_REQUESTED,
                JobStatus.BATCH_PROCESSING,
                JobStatus.DOWNLOADING,
                JobStatus.EXTRACTING,
                JobStatus.NORMALIZING,
                JobStatus.UPLOADING_TO_MINIO
            ]
            if job.status in active_statuses:
                raise ValueError(f"Cannot remove active scan in status {job.status}")
            db.delete(job)
            db.commit()
            return True
        finally:
            if close_db:
                db.close()

    @staticmethod
    def detect_crashed_jobs(timeout_minutes: int = 15, db: Optional[Session] = None) -> List[str]:
        """Flag active jobs with stale heartbeat as FAILED."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            cutoff = utc_now() - timedelta(minutes=timeout_minutes)
            active_statuses = [
                JobStatus.BATCH_REQUESTED,
                JobStatus.BATCH_PROCESSING,
                JobStatus.DOWNLOADING,
                JobStatus.EXTRACTING,
                JobStatus.NORMALIZING,
                JobStatus.UPLOADING_TO_MINIO
            ]
            crashed_jobs = db.query(Job).filter(
                Job.status.in_(active_statuses),
                Job.last_heartbeat < cutoff
            ).all()

            crashed_ids = []
            for j in crashed_jobs:
                j.status = JobStatus.FAILED
                j.error_message = f"Job crashed or timed out: no heartbeat for > {timeout_minutes} minutes"
                j.updated_at = utc_now()
                crashed_ids.append(j.id)
            if crashed_ids:
                db.commit()
            return crashed_ids
        finally:
            if close_db:
                db.close()


job_service = JobService()
