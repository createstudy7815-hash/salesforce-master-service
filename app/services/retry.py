import time
import random
import logging
import asyncio
from typing import Callable, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable(exc: Exception) -> bool:
    """Determine if an exception represents a transient/retryable network or HTTP error."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError, httpx.ReadTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return False


async def retry_call_async(
    fn: Callable[..., Any],
    *args,
    max_retries: int = 3,
    delays: Optional[List[int]] = None,
    jitter: bool = True,
    op_label: str = "operation",
    **kwargs
) -> Any:
    """Asynchronous bounded-retry executor with exponential backoff and jitter."""
    if delays is None:
        delays = [2, 5, 10]

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries or not is_retryable(exc):
                logger.error(f"[{op_label}] Failed on attempt {attempt + 1}/{max_retries + 1}. Error: {exc}")
                raise exc

            delay = delays[min(attempt, len(delays) - 1)]
            if jitter:
                delay = delay + random.uniform(0, 1)

            logger.warning(
                f"[{op_label}] Transient failure on attempt {attempt + 1}/{max_retries + 1}. "
                f"Retrying in {delay:.2f}s... Error: {exc}"
            )
            await asyncio.sleep(delay)

    raise last_exc


def retry_call_sync(
    fn: Callable[..., Any],
    *args,
    max_retries: int = 3,
    delays: Optional[List[int]] = None,
    jitter: bool = True,
    op_label: str = "operation",
    **kwargs
) -> Any:
    """Synchronous bounded-retry executor with backoff and jitter."""
    if delays is None:
        delays = [2, 5, 10]

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries or not is_retryable(exc):
                logger.error(f"[{op_label}] Failed on attempt {attempt + 1}/{max_retries + 1}. Error: {exc}")
                raise exc

            delay = delays[min(attempt, len(delays) - 1)]
            if jitter:
                delay = delay + random.uniform(0, 1)

            logger.warning(
                f"[{op_label}] Transient failure on attempt {attempt + 1}/{max_retries + 1}. "
                f"Retrying in {delay:.2f}s... Error: {exc}"
            )
            time.sleep(delay)

    raise last_exc
