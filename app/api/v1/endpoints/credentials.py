from fastapi import APIRouter, status
from app.schemas.auth import SalesforceCredentials, CredentialValidationResponse
from app.services.sf_auth import sf_auth_client

router = APIRouter()


@router.post(
    "/validate-credentials",
    response_model=CredentialValidationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Credentials"],
    summary="Validate Salesforce credentials without starting a scan"
)
async def validate_salesforce_credentials(
    credentials: SalesforceCredentials
):
    """
    Validates Salesforce OAuth credentials via real token grant + identity verification.
    Does NOT persist credentials or create a scan/job in PostgreSQL.
    """
    result = await sf_auth_client.validate_credentials(credentials)
    return result
