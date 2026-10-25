import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.retry import retry_call
from app.core.dlq import write_to_dlq

logger = logging.getLogger(__name__)


class MinIOClient:
    """
    MinIO / S3 client for publishing normalized tabular datasets (Parquet / JSON).
    Follows partitioned key format:
    salesforce/{table_name}/glynac_organization_id={org_id}/processing_date={date}/{table}.parquet
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        secure: Optional[bool] = None
    ):
        self.endpoint = endpoint or settings.MINIO_ENDPOINT
        self.access_key = access_key or settings.MINIO_ACCESS_KEY
        self.secret_key = secret_key or settings.MINIO_SECRET_KEY
        self.bucket_name = bucket_name or settings.MINIO_BUCKET
        self.secure = secure if secure is not None else settings.MINIO_SECURE

        try:
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
        except Exception as exc:
            logger.warning(f"Could not initialize MinIO client: {exc}")
            self.client = None

    def ensure_bucket_exists(self, bucket_name: Optional[str] = None) -> bool:
        """Create bucket if it doesn't already exist."""
        if not self.client:
            return False
        b_name = bucket_name or self.bucket_name

        def _check_and_create():
            if not self.client.bucket_exists(b_name):
                self.client.make_bucket(b_name)
                logger.info(f"Created MinIO bucket: {b_name}")
            return True

        try:
            return retry_call(
                _check_and_create,
                max_retries=settings.EXTERNAL_CALL_MAX_RETRIES,
                delays=settings.EXTERNAL_CALL_RETRY_DELAYS,
                jitter=settings.EXTERNAL_CALL_JITTER,
                op_label=f"MinIO ensure_bucket_exists({b_name})"
            )
        except Exception as exc:
            logger.error(f"Failed to ensure MinIO bucket {b_name}: {exc}")
            write_to_dlq(
                target_service="MinIO",
                operation="ensure_bucket_exists",
                payload={"bucket": b_name},
                attempts=settings.EXTERNAL_CALL_MAX_RETRIES,
                error=str(exc)
            )
            return False

    def upload_file(self, local_path: str, object_key: str, bucket_name: Optional[str] = None) -> str:
        """Upload a single file to MinIO."""
        if not self.client:
            raise RuntimeError("MinIO client is not configured or unavailable.")
        b_name = bucket_name or self.bucket_name
        self.ensure_bucket_exists(b_name)

        def _do_upload():
            self.client.fput_object(
                bucket_name=b_name,
                object_name=object_key,
                file_path=local_path
            )
            logger.info(f"Uploaded {local_path} to MinIO s3://{b_name}/{object_key}")
            return object_key

        try:
            return retry_call(
                _do_upload,
                max_retries=settings.EXTERNAL_CALL_MAX_RETRIES,
                delays=settings.EXTERNAL_CALL_RETRY_DELAYS,
                jitter=settings.EXTERNAL_CALL_JITTER,
                op_label=f"MinIO upload_file({object_key})"
            )
        except Exception as exc:
            write_to_dlq(
                target_service="MinIO",
                operation="upload_file",
                payload={"local_path": local_path, "object_key": object_key, "bucket": b_name},
                attempts=settings.EXTERNAL_CALL_MAX_RETRIES,
                error=str(exc)
            )
            raise

    def upload_directory(self, local_dir: str, prefix: str, bucket_name: Optional[str] = None) -> List[str]:
        """Upload all files in a directory under a key prefix."""
        uploaded_keys = []
        if not os.path.exists(local_dir):
            return uploaded_keys

        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
                obj_key = f"{prefix.rstrip('/')}/{rel_path}"
                uploaded_key = self.upload_file(local_path, obj_key, bucket_name)
                uploaded_keys.append(uploaded_key)

        return uploaded_keys

    def upload_normalized_data(
        self,
        scan_id: str,
        organization_id: str,
        processing_date: Optional[str],
        tables: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """
        Upload normalized table files to partitioned MinIO path:
        salesforce/{table_name}/glynac_organization_id={org_id}/processing_date={date}/{table}.parquet
        """
        if not processing_date:
            processing_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        uploaded_keys: List[str] = []

        for table_name, table_info in tables.items():
            file_path = table_info.get("file_path")
            if not file_path or not os.path.exists(file_path):
                continue

            file_ext = os.path.splitext(file_path)[1]
            object_key = (
                f"salesforce/{table_name}/"
                f"glynac_organization_id={organization_id}/"
                f"processing_date={processing_date}/"
                f"{table_name}{file_ext}"
            )
            key = self.upload_file(file_path, object_key)
            uploaded_keys.append(key)

        logger.info(f"Successfully uploaded {len(uploaded_keys)} tables for scan {scan_id} to MinIO.")
        return uploaded_keys


minio_client = MinIOClient()
