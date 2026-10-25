import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus
from app.services.job_service import job_service
from app.services.batch_file_service import batch_file_service
from app.services.minio_client import minio_client
from app.services.normalization import (
    NORMALIZER_REGISTRY,
    SUPPORTED_OBJECT_CATALOG,
    get_normalizer
)

logger = logging.getLogger(__name__)


class NormalizationService:
    """
    Transforms extracted raw Salesforce CSV datasets into clean, flat relational tables.
    Supports Parquet and JSON storage, per-object normalization, and automated MinIO publication.
    """

    def __init__(self):
        self.registry = NORMALIZER_REGISTRY
        self.catalog = SUPPORTED_OBJECT_CATALOG

    def get_supported_objects(self) -> List[Dict[str, Any]]:
        """Return static catalog of supported Salesforce objects and target tables."""
        return self.catalog

    def list_normalized_tables(self, scan_id: str) -> List[Dict[str, Any]]:
        """Return all persisted normalized tables and metadata for a scan."""
        return batch_file_service.list_normalized_tables(scan_id)

    async def normalize_scan(
        self,
        scan_id: str,
        format: str = "parquet",
        save_to_disk: bool = True,
        upload_to_minio: bool = False,
        processing_date: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Full scan normalization workflow:
        1. Transitions scan to status NORMALIZING
        2. Discovers all extracted CSV files for this scan
        3. Normalizes each object into relational tables (e.g. accounts, account_addresses)
        4. Saves output as Parquet or JSON
        5. Updates job state to NORMALIZED with complete table stats
        6. If upload_to_minio is True, uploads Parquet tables to MinIO and marks COMPLETED
        """
        job = job_service.get_job(scan_id, db=db)
        if not job:
            raise ValueError(f"Scan '{scan_id}' not found.")

        # 1. Transition state
        job_service.start_normalization(scan_id, db=db)
        logger.info(f"Starting normalization for scan {scan_id} (format={format}, save_to_disk={save_to_disk})")

        extracted_dir = batch_file_service.get_extracted_dir(scan_id)
        normalized_dir = batch_file_service.get_normalized_dir(scan_id)

        all_tables: Dict[str, List[Dict[str, Any]]] = {}
        table_stats: Dict[str, Dict[str, Any]] = {}

        try:
            # 2. Iterate through extracted CSV files
            csv_files = [f for f in os.listdir(extracted_dir) if f.endswith(".csv")]
            if not csv_files:
                logger.warning(f"No extracted CSV files found in {extracted_dir} for scan {scan_id}")

            for filename in csv_files:
                obj_name = filename[:-4]
                normalizer = get_normalizer(obj_name)
                if not normalizer:
                    logger.info(f"No custom normalizer registered for '{obj_name}', using default passthrough.")
                    continue

                csv_path = os.path.join(extracted_dir, filename)
                records, _ = batch_file_service.read_csv_file(csv_path)

                normalized_subtables = normalizer.normalize(records)

                for tbl_name, rows in normalized_subtables.items():
                    if tbl_name not in all_tables:
                        all_tables[tbl_name] = []
                    all_tables[tbl_name].extend(rows)

            # 3. Save to disk if requested
            if save_to_disk and all_tables:
                # Use base normalizer save_to_files
                from app.services.normalization.base import BaseNormalizer
                # Any normalizer instance can save tables
                sample_normalizer = list(self.registry.values())[0]
                table_stats = sample_normalizer.save_to_files(
                    tables=all_tables,
                    output_dir=normalized_dir,
                    format=format
                )
            elif all_tables:
                # Compute stats in memory if save_to_disk is false
                for tbl_name, rows in all_tables.items():
                    table_stats[tbl_name] = {
                        "table_name": tbl_name,
                        "file_name": None,
                        "file_path": None,
                        "format": format,
                        "row_count": len(rows),
                        "size_bytes": 0,
                        "columns": list(rows[0].keys()) if rows else []
                    }

            total_records = sum(len(rows) for rows in all_tables.values())
            normalization_summary = {
                "scan_id": scan_id,
                "format": format,
                "total_tables": len(all_tables),
                "total_records": total_records,
                "tables_generated": list(all_tables.keys()),
                "table_stats": table_stats,
                "normalized_at": datetime.now(timezone.utc).isoformat()
            }

            # 4. Mark job NORMALIZED
            job_service.complete_normalization(
                scan_id=scan_id,
                normalization_stats=normalization_summary,
                db=db
            )
            logger.info(f"Scan {scan_id} reached NORMALIZED status with {len(all_tables)} tables ({total_records} records).")

            # 5. MinIO upload step (if requested)
            if upload_to_minio:
                job_service.start_minio_upload(scan_id, db=db)
                uploaded_keys = minio_client.upload_normalized_data(
                    scan_id=scan_id,
                    organization_id=job.organization_id,
                    processing_date=processing_date,
                    tables=table_stats
                )
                job_service.complete_minio_upload(
                    scan_id=scan_id,
                    minio_object_keys=uploaded_keys,
                    mark_completed=True,
                    db=db
                )
                normalization_summary["minio_uploaded"] = True
                normalization_summary["minio_object_keys"] = uploaded_keys

            return normalization_summary

        except Exception as exc:
            logger.error(f"Normalization failed for scan {scan_id}: {exc}", exc_info=True)
            job_service.fail_job(scan_id, error=f"Normalization failed: {exc}", db=db)
            raise

    async def normalize_single_object(
        self,
        scan_id: str,
        object_name: str,
        format: str = "parquet",
        save_to_disk: bool = True,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Normalize a single extracted Salesforce object for a given scan.
        """
        job = job_service.get_job(scan_id, db=db)
        if not job:
            raise ValueError(f"Scan '{scan_id}' not found.")

        normalizer = get_normalizer(object_name)
        if not normalizer:
            raise ValueError(f"No normalizer available for Salesforce object '{object_name}'.")

        extracted_dir = batch_file_service.get_extracted_dir(scan_id)
        csv_path = os.path.join(extracted_dir, f"{object_name}.csv")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Extracted CSV for '{object_name}' not found at {csv_path}")

        records, _ = batch_file_service.read_csv_file(csv_path)
        tables = normalizer.normalize(records)

        table_stats = {}
        if save_to_disk:
            normalized_dir = batch_file_service.get_normalized_dir(scan_id)
            table_stats = normalizer.save_to_files(tables, normalized_dir, format=format)
        else:
            for tbl_name, rows in tables.items():
                table_stats[tbl_name] = {
                    "table_name": tbl_name,
                    "format": format,
                    "row_count": len(rows),
                    "size_bytes": 0,
                    "columns": list(rows[0].keys()) if rows else []
                }

        total_records = sum(len(rows) for rows in tables.values())
        return {
            "scan_id": scan_id,
            "object_name": object_name,
            "format": format,
            "total_tables": len(tables),
            "total_records": total_records,
            "tables_generated": list(tables.keys()),
            "table_stats": table_stats
        }


normalization_service = NormalizationService()
