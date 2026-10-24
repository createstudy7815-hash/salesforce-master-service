import asyncio
import time
import logging
from typing import Dict, List, Optional, Any

from app.core.config import settings
from app.models.job import JobStatus
from app.schemas.auth import SalesforceCredentials
from app.services.job_service import job_service
from app.services.sf_batch_client import sf_batch_client
from app.services.batch_file_service import batch_file_service

logger = logging.getLogger(__name__)


class BatchPollingService:
    """
    Coordinates Bulk API 2.0 query job creation, async polling,
    and automatic CSV result downloading.
    """
    def __init__(self):
        self.poll_interval = settings.SF_BULK_POLL_INTERVAL_SECONDS
        self.max_wait_minutes = settings.SF_BULK_MAX_WAIT_MINUTES

    async def submit_batch_jobs(
        self,
        scan_id: str,
        objects: List[str],
        creds: SalesforceCredentials,
        soql_queries: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Creates one Bulk API 2.0 query job per configured object.
        Persists job IDs on the Job row.
        """
        batch_job_ids = {}
        queries = soql_queries or {}

        for obj in objects:
            soql = queries.get(obj)
            res = await sf_batch_client.create_query_job(
                object_name=obj,
                creds=creds,
                soql=soql
            )
            batch_job_ids[obj] = res["id"]

        job_service.update_batch_info(
            scan_id=scan_id,
            batch_job_ids=batch_job_ids,
            batch_status="SUBMITTED"
        )
        logger.info(f"Scan {scan_id}: Submitted {len(batch_job_ids)} Bulk API jobs: {batch_job_ids}")
        return batch_job_ids

    async def poll_until_ready(
        self,
        scan_id: str,
        creds: SalesforceCredentials,
        max_wait_minutes: Optional[int] = None,
        check_interval_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Polls all sub-jobs until all are JobComplete, refreshing heartbeat each iteration.
        """
        max_wait = (max_wait_minutes or self.max_wait_minutes) * 60
        interval = check_interval_seconds or self.poll_interval
        start_time = time.time()

        job_service.update_job_status(scan_id, JobStatus.BATCH_PROCESSING)

        while time.time() - start_time < max_wait:
            # Refresh heartbeat
            job_service.update_heartbeat(scan_id)

            job = job_service.get_job(scan_id)
            if not job or job.status == JobStatus.CANCELLED:
                logger.warning(f"Scan {scan_id} was cancelled during batch polling.")
                return {"status": "CANCELLED"}

            batch_jobs = job.batch_job_ids or {}
            all_complete = True
            states = {}

            for obj_name, remote_job_id in batch_jobs.items():
                status_res = await sf_batch_client.get_job_status(remote_job_id, creds)
                state = status_res.get("state")
                states[obj_name] = state

                if state in ("Failed", "Aborted"):
                    err_msg = status_res.get("errorMessage") or f"Bulk API job for {obj_name} entered state {state}"
                    logger.error(f"Scan {scan_id}: {err_msg}")
                    job_service.fail_job(scan_id, error=err_msg)
                    raise RuntimeError(err_msg)

                if state != "JobComplete":
                    all_complete = False

            if all_complete:
                logger.info(f"Scan {scan_id}: All {len(batch_jobs)} Bulk API jobs completed successfully!")
                job_service.update_job_status(scan_id, JobStatus.BATCH_READY)
                return {"status": "JobComplete", "states": states}

            await asyncio.sleep(interval)

        timeout_err = f"Scan {scan_id}: Bulk API jobs did not complete within {max_wait // 60} minutes."
        job_service.fail_job(scan_id, error=timeout_err)
        raise TimeoutError(timeout_err)

    async def download_results(
        self,
        scan_id: str,
        creds: SalesforceCredentials
    ) -> List[str]:
        """
        Downloads CSV results for all completed Bulk API jobs and saves to disk.
        """
        job = job_service.get_job(scan_id)
        if not job or not job.batch_job_ids:
            raise ValueError(f"Scan {scan_id} has no batch jobs to download.")

        job_service.update_job_status(scan_id, JobStatus.DOWNLOADING)
        file_paths = []
        file_sizes = {}
        record_counts = {}

        for obj_name, remote_job_id in job.batch_job_ids.items():
            job_service.update_heartbeat(scan_id)
            locator = None
            full_csv_chunks = []

            while True:
                chunk_csv, next_loc = await sf_batch_client.get_job_results(
                    job_id=remote_job_id,
                    creds=creds,
                    locator=locator
                )
                full_csv_chunks.append(chunk_csv)
                if not next_loc:
                    break
                locator = next_loc

            combined_csv = "".join(full_csv_chunks)
            saved_path = batch_file_service.save_results_to_disk(
                scan_id=scan_id,
                object_name=obj_name,
                csv_content=combined_csv
            )
            file_paths.append(saved_path)
            file_sizes[obj_name] = len(combined_csv.encode("utf-8"))

            # Count rows
            lines = combined_csv.strip().split("\n")
            record_counts[obj_name] = max(0, len(lines) - 1) if lines and lines[0] else 0

        # Mark downloaded and record file stats
        job_service.update_download_info(
            scan_id=scan_id,
            file_paths=file_paths,
            file_sizes=file_sizes
        )
        return file_paths


batch_polling_service = BatchPollingService()
