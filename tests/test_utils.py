import uuid
from decimal import Decimal
from datetime import datetime, timezone
import enum
import pytest

from app.core.utils import (
    deep_serialize,
    calculate_duration,
    build_pagination_info,
    Encrypter
)


class DummyEnum(enum.Enum):
    ALPHA = "alpha"
    BETA = "beta"


def test_deep_serialize():
    now = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
    raw = {
        "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
        "amount": Decimal("199.99"),
        "enum": DummyEnum.ALPHA,
        "date": now,
        "nested": {
            "tags": ["tag1", Decimal("42.5")],
            "null_val": None
        }
    }
    serialized = deep_serialize(raw)
    assert serialized["id"] == "12345678-1234-5678-1234-567812345678"
    assert serialized["amount"] == 199.99
    assert serialized["enum"] == "alpha"
    assert "2026-10-25" in serialized["date"]
    assert serialized["nested"]["tags"] == ["tag1", 42.5]
    assert serialized["nested"]["null_val"] is None


def test_calculate_duration():
    start = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 25, 12, 1, 30, tzinfo=timezone.utc)
    diff = calculate_duration(start, end)
    assert diff == 90.0

    # With ISO string timestamps
    diff_str = calculate_duration("2026-10-25T12:00:00Z", "2026-10-25T12:00:45Z")
    assert diff_str == 45.0

    assert calculate_duration(None) is None


def test_build_pagination_info():
    info = build_pagination_info(page=2, page_size=10, total=35)
    assert info["page"] == 2
    assert info["page_size"] == 10
    assert info["total"] == 35
    assert info["total_pages"] == 4
    assert info["has_next"] is True
    assert info["has_prev"] is True

    # First page
    info_first = build_pagination_info(page=1, page_size=20, total=15)
    assert info_first["total_pages"] == 1
    assert info_first["has_next"] is False
    assert info_first["has_prev"] is False


def test_encrypter():
    enc = Encrypter("secret-passphrase-key-salesforce")
    plain = "sensitive-oauth-client-secret-12345"
    token = enc.encrypt(plain)
    assert token != plain
    decrypted = enc.decrypt(token)
    assert decrypted == plain
