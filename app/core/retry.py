import asyncio
import inspect
import logging
import random
import time
from typing import Callable, Any, Optional, List
import httpx

from app.core.config import settings
from app.core.dlq import write_to_dlq

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable(exc: Exception) -> bool:
    """
    Classifies transient failures:
    - Connection errors / network disconnects
    - Timeouts
    - Transient HTTP status codes: 408, 429, 500, 502, 503, 504
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, TimeoutError, ConnectionError)):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES

    # Generic check if exception has status_code or response.status_code
    status_code = getattr(exc, "status_code", None)
    if status_code is None and hasattr(exc, "response"):
        status_code = getattr(exc.response, "status_code", None)

    if status_code and status_code in RETRYABLE_STATUS_CODES:
        return True

    return False


async def retry_call(
    fn: Callable,
    max_retries: Optional[int] = None,
    delays: Optional[List[float]] = None,
    jitter: Optional[bool] = None,
    op_label: str = "external_call",
    target_service: Optional[str] = None,
    payload: Optional[Any] = None,
    organization_id: Optional[str] = None,
    scan_id: Optional[str] = None,
    db: Optional[Any] = None,
    *args,
    **kwargs
) -> Any:
    """
    Execute a callable (async or sync) with bounded exponential backoff and jitter.
    If retries are exhausted, automatically writes to the DLQ and re-raises the exception.
    """
    if max_retries is None:
        max_retries = getattr(settings, "EXTERNAL_CALL_MAX_RETRIES", 3)
    if delays is None:
        delays = getattr(settings, "EXTERNAL_CALL_RETRY_DELAYS", [0.1, 0.2, 0.4])
    if jitter is None:
        jitter = getattr(settings, "EXTERNAL_CALL_JITTER", True)

    attempts = 0
    total_allowed = max_retries + 1  # 1 initial try + retries
    last_exc = None

    is_async = inspect.iscoroutinefunction(fn)

    while attempts < total_allowed:
        attempts += 1
        try:
            if is_async:
                return await fn(*args, **kwargs)
            else:
                return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempts >= total_allowed or not is_retryable(exc):
                # Cannot retry or retries exhausted
                logger.warning(
                    f"[{op_label}] Call failed after {attempts} attempts. Non-retryable or retries exhausted: {exc}"
                )
                if target_service:
                    write_to_dlq(
                        target_service=target_service,
                        operation=op_label,
                        payload=payload or kwargs or args,
                        attempts=attempts,
                        error=str(exc),
                        organization_id=organization_id,
                        scan_id=scan_id,
                        db=db
                    )
                raise exc

            # Calculate backoff delay
            delay_idx = min(attempts - 1, len(delays) - 1)
            base_delay = delays[delay_idx]
            sleep_time = base_delay + (random.uniform(0, 0.1 * base_delay) if jitter else 0.0)

            logger.info(
                f"[{op_label}] Transient error ({exc}). Attempt {attempts}/{total_allowed}. Retrying in {sleep_time:.2f}s..."
            )
            await asyncio.sleep(sleep_time)

    # Fallback in case loop exits without return/raise
    if last_exc:
        raise last_exc
