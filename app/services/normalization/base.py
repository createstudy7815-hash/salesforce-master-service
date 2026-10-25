import os
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
import pandas as pd

logger = logging.getLogger(__name__)


class BaseNormalizer(ABC):
    """
    Abstract base class for Salesforce object normalizers.
    Provides robust parsing, type-casting, sanitization, and serialization helpers.
    """

    @abstractmethod
    def normalize(self, records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Transform raw Salesforce records into one or more flat, relational tables.
        Returns mapping of {table_name: [rows]}.
        """
        pass

    @staticmethod
    def safe_get(
        record: Dict[str, Any],
        keys: Union[str, List[str]],
        default: Any = None
    ) -> Any:
        """
        Fetch value by trying one or more key names case-insensitively.
        Returns first non-empty value or default.
        """
        if isinstance(keys, str):
            keys = [keys]

        lower_record = {k.lower(): v for k, v in record.items()}

        for key in keys:
            # Exact match first
            if key in record and record[key] not in (None, ""):
                return record[key]
            # Case-insensitive match
            k_low = key.lower()
            if k_low in lower_record and lower_record[k_low] not in (None, ""):
                return lower_record[k_low]

        return default

    @staticmethod
    def clean_string(val: Any) -> Optional[str]:
        """Strip whitespace and convert empty values to None."""
        if val is None:
            return None
        s = str(val).strip()
        return s if s else None

    @staticmethod
    def clean_bool(val: Any) -> Optional[bool]:
        """Safely parse boolean values from various Salesforce formats."""
        if val is None or val == "":
            return None
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        if s in ("true", "1", "t", "yes", "y"):
            return True
        if s in ("false", "0", "f", "no", "n"):
            return False
        return None

    @staticmethod
    def clean_int(val: Any) -> Optional[int]:
        """Safely parse integer values."""
        if val is None or val == "":
            return None
        try:
            return int(float(str(val).strip()))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def clean_float(val: Any) -> Optional[float]:
        """Safely parse floating point currency/metric values."""
        if val is None or val == "":
            return None
        try:
            # Strip currency symbols if present
            s = str(val).replace("$", "").replace(",", "").strip()
            return round(float(s), 4)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def clean_date(val: Any) -> Optional[str]:
        """Format dates/datetimes to ISO-8601 strings."""
        if val is None or val == "":
            return None
        s = str(val).strip()
        try:
            # Common Salesforce formats
            if "T" in s:
                # e.g., 2026-10-25T12:00:00.000+0000 or Z
                clean_s = s.replace("+0000", "+00:00").replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_s)
            else:
                dt = datetime.strptime(s[:10], "%Y-%m-%d")
            return dt.isoformat()
        except Exception:
            return s  # Return original if unable to parse

    def save_to_files(
        self,
        tables: Dict[str, List[Dict[str, Any]]],
        output_dir: str,
        format: str = "parquet"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Persist normalized tables to disk in Parquet or JSON format.
        Returns stats dict with row counts, file sizes, and columns per table.
        """
        os.makedirs(output_dir, exist_ok=True)
        stats = {}

        for table_name, rows in tables.items():
            fmt = format.lower()
            file_name = f"{table_name}.{fmt}"
            file_path = os.path.join(output_dir, file_name)

            if fmt == "parquet":
                df = pd.DataFrame(rows) if rows else pd.DataFrame()
                df.to_parquet(file_path, engine="pyarrow", index=False)
            elif fmt == "json":
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}. Use 'parquet' or 'json'.")

            size_bytes = os.path.getsize(file_path)
            columns = list(rows[0].keys()) if rows else []

            stats[table_name] = {
                "table_name": table_name,
                "file_name": file_name,
                "file_path": file_path,
                "format": fmt,
                "row_count": len(rows),
                "size_bytes": size_bytes,
                "columns": columns
            }
            logger.info(f"Saved normalized table '{table_name}' ({len(rows)} rows, {size_bytes} bytes) to {file_path}")

        return stats

    @staticmethod
    def get_statistics(tables: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Aggregate total tables and record counts from normalized tables."""
        total_records = sum(len(rows) for rows in tables.values())
        return {
            "total_tables": len(tables),
            "total_records": total_records,
            "table_record_counts": {tbl: len(rows) for tbl, rows in tables.items()}
        }
