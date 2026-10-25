import os
import csv
import shutil
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DATA_DIR = os.path.join(os.getcwd(), "data", "scans")


class BatchFileService:
    def __init__(self, base_dir: str = BASE_DATA_DIR):
        self.base_dir = base_dir

    def get_extracted_dir(self, scan_id: str) -> str:
        extracted_dir = os.path.join(self.base_dir, scan_id, "extracted")
        os.makedirs(extracted_dir, exist_ok=True)
        return extracted_dir

    def save_results_to_disk(self, scan_id: str, object_name: str, csv_content: str) -> str:
        """
        Save raw CSV text to data/scans/{scan_id}/extracted/{object_name}.csv
        """
        extracted_dir = self.get_extracted_dir(scan_id)
        file_path = os.path.join(extracted_dir, f"{object_name}.csv")
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)
        logger.info(f"Saved {object_name} CSV ({len(csv_content)} bytes) to {file_path}")
        return file_path

    def read_csv_file(
        self,
        path: str,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Read CSV records with optional pagination.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        records = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            records = list(reader)

        total = len(records)
        if page is not None and page_size is not None:
            offset = (page - 1) * page_size
            records = records[offset:offset + page_size]

        return records, total

    def get_file_info(self, scan_id: str) -> Dict[str, Any]:
        """
        List extracted files, record counts, and sizes in bytes.
        """
        extracted_dir = os.path.join(self.base_dir, scan_id, "extracted")
        if not os.path.exists(extracted_dir):
            return {"file_paths": [], "file_sizes": {}, "record_counts": {}}

        file_paths = []
        file_sizes = {}
        record_counts = {}

        for filename in os.listdir(extracted_dir):
            if filename.endswith(".csv"):
                obj_name = filename[:-4]
                full_path = os.path.join(extracted_dir, filename)
                file_paths.append(full_path)
                file_sizes[obj_name] = os.path.getsize(full_path)
                
                with open(full_path, "r", encoding="utf-8") as f:
                    # Subtract 1 for header line if file is non-empty
                    lines = sum(1 for _ in f)
                    record_counts[obj_name] = max(0, lines - 1) if lines > 0 else 0

        return {
            "file_paths": file_paths,
            "file_sizes": file_sizes,
            "record_counts": record_counts
        }

    def infer_schema(self, path: str, sample_size: int = 100) -> Dict[str, str]:
        """
        Infer field types (integer, float, boolean, string) from first N rows.
        """
        records, _ = self.read_csv_file(path, page=1, page_size=sample_size)
        if not records:
            return {}

        schema = {}
        for col in records[0].keys():
            col_type = "string"
            values = [r[col] for r in records if r[col] not in (None, "")]
            if values:
                if all(v.lower() in ("true", "false", "0", "1") for v in values):
                    col_type = "boolean"
                elif all(v.isdigit() or (v.startswith("-") and v[1:].isdigit()) for v in values):
                    col_type = "integer"
                else:
                    try:
                        all(float(v) for v in values)
                        col_type = "float"
                    except ValueError:
                        col_type = "string"
            schema[col] = col_type

        return schema

    def get_normalized_dir(self, scan_id: str) -> str:
        """
        Get or create directory data/scans/{scan_id}/normalized/
        """
        normalized_dir = os.path.join(self.base_dir, scan_id, "normalized")
        os.makedirs(normalized_dir, exist_ok=True)
        return normalized_dir

    def list_normalized_tables(self, scan_id: str) -> List[Dict[str, Any]]:
        """
        List all normalized Parquet/JSON table files for a scan with file sizes and row counts.
        """
        normalized_dir = os.path.join(self.base_dir, scan_id, "normalized")
        if not os.path.exists(normalized_dir):
            return []

        tables = []
        for filename in sorted(os.listdir(normalized_dir)):
            if filename.endswith(".parquet") or filename.endswith(".json"):
                full_path = os.path.join(normalized_dir, filename)
                name, ext = os.path.splitext(filename)
                fmt = ext.lstrip(".").lower()
                size_bytes = os.path.getsize(full_path)

                record_count = 0
                try:
                    if fmt == "parquet":
                        import pyarrow.parquet as pq
                        meta = pq.read_metadata(full_path)
                        record_count = meta.num_rows
                    elif fmt == "json":
                        import json
                        with open(full_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            record_count = len(data) if isinstance(data, list) else 1
                except Exception as exc:
                    logger.warning(f"Could not read row count for {full_path}: {exc}")
                    record_count = 0

                tables.append({
                    "table_name": name,
                    "file_name": filename,
                    "format": fmt,
                    "size_bytes": size_bytes,
                    "record_count": record_count,
                    "file_path": full_path
                })
        return tables

    def cleanup_extracted_files(self, scan_id: str) -> bool:
        """
        Delete scan data folder.
        """
        scan_dir = os.path.join(self.base_dir, scan_id)
        if os.path.exists(scan_dir):
            shutil.rmtree(scan_dir, ignore_errors=True)
            logger.info(f"Cleaned up scan files for {scan_id}")
            return True
        return False


batch_file_service = BatchFileService()
