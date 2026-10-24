from fastapi import APIRouter, Depends
from app.core.config import settings
from app.core.hmac_auth import hmac_auth_required, HMACClient
from app.schemas.batch import BatchInfoResponse
from app.services.sf_batch_client import DEFAULT_SOQL_QUERIES

router = APIRouter()


@router.get(
    "/info",
    response_model=BatchInfoResponse,
    summary="Get configured Bulk API 2.0 settings and default queries"
)
def get_batch_info(
    client: HMACClient = Depends(hmac_auth_required)
):
    """
    Returns configured Bulk API settings: supported Salesforce objects,
    polling intervals, and standard SOQL query defaults.
    """
    return BatchInfoResponse(
        api_version=settings.SF_API_VERSION,
        supported_objects=settings.SF_SUPPORTED_OBJECTS,
        default_poll_interval_seconds=settings.SF_BULK_POLL_INTERVAL_SECONDS,
        max_wait_minutes=settings.SF_BULK_MAX_WAIT_MINUTES,
        query_defaults=DEFAULT_SOQL_QUERIES
    )
