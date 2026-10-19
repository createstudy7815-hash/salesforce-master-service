import pytest
import httpx
from unittest.mock import AsyncMock
from app.core.retry import is_retryable, retry_call
from app.core.dlq import scrub_payload, write_to_dlq
from app.models.dlq import FailedExternalCall


def test_is_retryable_classification():
    # Transient network/timeout errors
    assert is_retryable(httpx.ConnectTimeout("connection timed out")) is True
    assert is_retryable(httpx.ReadTimeout("read timed out")) is True
    assert is_retryable(httpx.ConnectError("cannot connect")) is True

    # Transient HTTP errors
    req = httpx.Request("POST", "https://api.salesforce.com")
    resp_503 = httpx.Response(503, request=req)
    assert is_retryable(httpx.HTTPStatusError("Service Unavailable", request=req, response=resp_503)) is True

    resp_429 = httpx.Response(429, request=req)
    assert is_retryable(httpx.HTTPStatusError("Too Many Requests", request=req, response=resp_429)) is True

    # Non-retryable errors
    resp_400 = httpx.Response(400, request=req)
    assert is_retryable(httpx.HTTPStatusError("Bad Request", request=req, response=resp_400)) is False

    resp_401 = httpx.Response(401, request=req)
    assert is_retryable(httpx.HTTPStatusError("Unauthorized", request=req, response=resp_401)) is False

    assert is_retryable(ValueError("Invalid argument")) is False


@pytest.mark.asyncio
async def test_retry_call_success_on_second_attempt():
    attempts = 0

    async def flaky_fn():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectTimeout("timeout")
        return "success"

    result = await retry_call(flaky_fn, max_retries=2, delays=[0.01, 0.01], jitter=False)
    assert result == "success"
    assert attempts == 2


@pytest.mark.asyncio
async def test_retry_call_non_retryable_fails_immediately():
    attempts = 0

    async def invalid_fn():
        nonlocal attempts
        attempts += 1
        raise ValueError("Non-retryable fault")

    with pytest.raises(ValueError, match="Non-retryable fault"):
        await retry_call(invalid_fn, max_retries=3, delays=[0.01], jitter=False)

    assert attempts == 1


@pytest.mark.asyncio
async def test_retry_call_exhaustion_writes_to_dlq(db_session):
    async def always_failing():
        raise httpx.ConnectError("Salesforce down")

    with pytest.raises(httpx.ConnectError):
        await retry_call(
            always_failing,
            max_retries=2,
            delays=[0.01, 0.01],
            jitter=False,
            op_label="test_exhaustion",
            target_service="salesforce",
            organization_id="00DTestOrg",
            payload={"password": "supersecretpassword", "username": "admin@test.com"},
            db=db_session
        )

    # Check DLQ recorded
    failed = db_session.query(FailedExternalCall).filter(
        FailedExternalCall.operation == "test_exhaustion"
    ).first()
    assert failed is not None
    assert failed.target_service == "salesforce"
    assert failed.organization_id == "00DTestOrg"
    assert failed.attempts == 3
    assert "supersecretpassword" not in failed.payload
    assert "******" in failed.payload


def test_scrub_payload():
    data = {
        "client_id": "12345",
        "client_secret": "my-secret-key",
        "username": "user@domain.com",
        "nested": {
            "password": "p@ssword",
            "security_token": "token123",
            "safe_field": "visible_value"
        },
        "items": [
            {"access_token": "bearer-token-abc", "count": 5}
        ]
    }
    scrubbed = scrub_payload(data)
    assert scrubbed["client_id"] == "12345"
    assert scrubbed["client_secret"] == "******"
    assert scrubbed["nested"]["password"] == "******"
    assert scrubbed["nested"]["security_token"] == "******"
    assert scrubbed["nested"]["safe_field"] == "visible_value"
    assert scrubbed["items"][0]["access_token"] == "******"
    assert scrubbed["items"][0]["count"] == 5
