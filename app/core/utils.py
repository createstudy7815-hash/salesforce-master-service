import uuid
from decimal import Decimal
from enum import Enum
from datetime import datetime, date, timezone
from typing import Any, Dict, Optional, Union
import base64
from cryptography.fernet import Fernet


def deep_serialize(obj: Any) -> Any:
    """
    Recursively converts Decimals, UUIDs, Enums, and datetimes
    into JSON-safe native Python types (strings, floats, ints, dicts, lists).
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [deep_serialize(item) for item in obj]
    if hasattr(obj, "__dict__"):
        return deep_serialize(vars(obj))
    return str(obj)


def calculate_duration(
    start: Optional[Union[datetime, str]],
    end: Optional[Union[datetime, str]] = None
) -> Optional[float]:
    """
    Calculate duration in seconds between two timestamps.
    Accepts datetime objects or ISO-8601 strings.
    If end is omitted, uses current UTC time.
    """
    if not start:
        return None

    def _parse_ts(val: Union[datetime, str]) -> datetime:
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    try:
        start_dt = _parse_ts(start)
        end_dt = _parse_ts(end) if end else datetime.now(timezone.utc)
        delta = end_dt - start_dt
        return round(max(0.0, delta.total_seconds()), 2)
    except Exception:
        return None


def build_pagination_info(page: int, page_size: int, total: int) -> Dict[str, Any]:
    """
    Build standard pagination metadata envelope.
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    return {
        "page": max(1, page),
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, total_pages),
        "has_next": (page * page_size) < total,
        "has_prev": page > 1
    }


class Encrypter:
    """
    Fernet symmetric encryption utility for sensitive configs or secrets stored at rest.
    Uses provided 32-byte URL-safe base64 key or generates a deterministic key from passphrase.
    """
    def __init__(self, key: Optional[str] = None):
        if not key:
            key = Fernet.generate_key().decode("utf-8")
        elif len(key) != 44 or not key.endswith("="):
            # If a custom passphrase is provided, derive a valid 32-byte Fernet key
            key_bytes = key.encode("utf-8")
            padded = key_bytes.ljust(32, b"0")[:32]
            key = base64.urlsafe_b64encode(padded).decode("utf-8")
        self.key = key
        self.fernet = Fernet(key.encode("utf-8") if isinstance(key, str) else key)

    def encrypt(self, plain_text: str) -> str:
        """Encrypt plain text to base64 Fernet token."""
        return self.fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")

    def decrypt(self, cipher_token: str) -> str:
        """Decrypt Fernet token back to plain text."""
        return self.fernet.decrypt(cipher_token.encode("utf-8")).decode("utf-8")
