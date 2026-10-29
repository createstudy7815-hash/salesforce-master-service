import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.retry import retry_call_sync
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

    def check_connection(self, timeout: float = 1.0) -> bool:
        """
        Verify reachability and connectivity to the MinIO cluster with a quick timeout.
        Returns True if MinIO is responsive, False otherwise.
        """
        if not self.endpoint:
            return False
        try:
            import socket
            endpoint = self.endpoint.replace("http://", "").replace("https://", "")
            if ":" in endpoint:
                host, port_str = endpoint.split(":", 1)
                port = int(port_str.split("/")[0])
            else:
                host = endpoint
                port = 443 if self.secure else 9000
            s = socket.create_connection((host, port), timeout=timeout)
            s.close()
            return True
        except Exception as exc:
            logger.debug(f"MinIO health check probe failed: {exc}")
            return False

    def ensure_bucket_exists(self, bucket_name: Optional[str] = None, db: Optional[Any] = None) -> bool:
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
            return retry_call_sync(
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
                error=str(exc),
                db=db
            )
            return False

    def upload_file(
        self,
        local_path: str,
        object_key: str,
        bucket_name: Optional[str] = None,
        db: Optional[Any] = None
    ) -> str:
        """Upload a single file to MinIO."""
        if not self.client:
            raise RuntimeError("MinIO client is not configured or unavailable.")
        b_name = bucket_name or self.bucket_name
        self.ensure_bucket_exists(b_name, db=db)

        def _do_upload():
            self.client.fput_object(
                bucket_name=b_name,
                object_name=object_key,
                file_path=local_path
            )
            logger.info(f"Uploaded {local_path} to MinIO s3://{b_name}/{object_key}")
            return object_key

        try:
            return retry_call_sync(
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
                error=str(exc),
                db=db
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

    def download_file(self, object_key: str, local_path: str, bucket_name: Optional[str] = None) -> str:
        """Download a single object from MinIO."""
        if not self.client:
            raise RuntimeError("MinIO client is not configured or unavailable.")
        b_name = bucket_name or self.bucket_name

        def _do_download():
            parent_dir = os.path.dirname(local_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            self.client.fget_object(
                bucket_name=b_name,
                object_name=object_key,
                file_path=local_path
            )
            logger.info(f"Downloaded MinIO s3://{b_name}/{object_key} to {local_path}")
            return local_path

        try:
            return retry_call_sync(
                _do_download,
                max_retries=settings.EXTERNAL_CALL_MAX_RETRIES,
                delays=settings.EXTERNAL_CALL_RETRY_DELAYS,
                jitter=settings.EXTERNAL_CALL_JITTER,
                op_label=f"MinIO download_file({object_key})"
            )
        except Exception as exc:
            write_to_dlq(
                target_service="MinIO",
                operation="download_file",
                payload={"object_key": object_key, "local_path": local_path, "bucket": b_name},
                attempts=settings.EXTERNAL_CALL_MAX_RETRIES,
                error=str(exc)
            )
            raise

    def list_objects(self, prefix: str = "", recursive: bool = True, bucket_name: Optional[str] = None) -> List[str]:
        """List object keys under a prefix."""
        if not self.client:
            return []
        b_name = bucket_name or self.bucket_name
        try:
            objects = self.client.list_objects(b_name, prefix=prefix, recursive=recursive)
            return [obj.object_name for obj in objects]
        except Exception as exc:
            logger.error(f"Failed to list MinIO objects under prefix '{prefix}': {exc}")
            return []

    def delete_object(self, object_key: str, bucket_name: Optional[str] = None) -> bool:
        """Delete an object from MinIO."""
        if not self.client:
            return False
        b_name = bucket_name or self.bucket_name
        try:
            self.client.remove_object(b_name, object_key)
            logger.info(f"Deleted MinIO object s3://{b_name}/{object_key}")
            return True
        except Exception as exc:
            logger.error(f"Failed to delete MinIO object {object_key}: {exc}")
            return False

    def upload_normalized_data(
        self,
        scan_id: str,
        organization_id: str,
        processing_date: Optional[str] = None,
        tables: Optional[Dict[str, Any]] = None,
        db: Optional[Any] = None
    ) -> List[str]:
        """
        Upload normalized table files to partitioned MinIO path:
        salesforce/{table_name}/glynac_organization_id={org_id}/processing_date={date}/{table}.parquet
        """
        if not processing_date:
            processing_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Fallback to local normalized folder if tables dict not provided
        if not tables:
            from app.services.batch_file_service import batch_file_service
            norm_dir = batch_file_service.get_normalized_dir(scan_id)
            if os.path.exists(norm_dir):
                tables = {}
                for f in os.listdir(norm_dir):
                    if f.endswith(".parquet") or f.endswith(".json"):
                        tbl_name = os.path.splitext(f)[0]
                        tables[tbl_name] = {"file_path": os.path.join(norm_dir, f)}

        if not tables:
            logger.warning(f"No normalized tables available to upload for scan {scan_id}")
            return []

        uploaded_keys: List[str] = []

        for table_name, table_info in tables.items():
            if isinstance(table_info, str):
                file_path = table_info
            elif isinstance(table_info, dict):
                file_path = table_info.get("file_path")
            else:
                continue

            if not file_path or not os.path.exists(file_path):
                continue

            file_ext = os.path.splitext(file_path)[1]
            object_key = (
                f"salesforce/{table_name}/"
                f"glynac_organization_id={organization_id}/"
                f"processing_date={processing_date}/"
                f"{table_name}{file_ext}"
            )
            key = self.upload_file(file_path, object_key, db=db)
            uploaded_keys.append(key)

        logger.info(f"Successfully uploaded {len(uploaded_keys)} tables for scan {scan_id} to MinIO.")
        return uploaded_keys


minio_client = MinIOClient()
