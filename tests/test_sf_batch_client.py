import pytest
import respx
import httpx
from app.schemas.auth import SalesforceCredentials, TokenResponse
from app.services.sf_batch_client import sf_batch_client
from app.services.sf_auth import sf_auth_client


@pytest.fixture
def mock_creds():
    return SalesforceCredentials(
        login_url="https://test.salesforce.com",
        client_id="test_client_id",
        username="admin@test.com",
        password="test_password"
    )


@pytest.fixture(autouse=True)
def mock_token(mock_creds):
    token_resp = TokenResponse(
        access_token="mock_access_token_123",
        instance_url="https://company.my.salesforce.com",
        id="https://test.salesforce.com/id/00DOrg/005User",
        token_type="Bearer"
    )
    cache_key = sf_auth_client._get_cache_key(mock_creds)
    from app.services.sf_auth import CachedToken
    sf_auth_client._token_cache[cache_key] = CachedToken(token_resp)
    yield
    sf_auth_client.clear_cache()


@pytest.mark.asyncio
@respx.mock
async def test_create_query_job(mock_creds):
    respx.post("https://company.my.salesforce.com/services/data/v60.0/jobs/query").respond(
        200,
        json={
            "id": "7500000001",
            "operation": "query",
            "object": "Account",
            "state": "UploadComplete"
        }
    )

    result = await sf_batch_client.create_query_job(
        object_name="Account",
        creds=mock_creds,
        soql="SELECT Id, Name FROM Account"
    )
    assert result["id"] == "7500000001"
    assert result["state"] == "UploadComplete"


@pytest.mark.asyncio
@respx.mock
async def test_get_job_status(mock_creds):
    respx.get("https://company.my.salesforce.com/services/data/v60.0/jobs/query/7500000001").respond(
        200,
        json={
            "id": "7500000001",
            "state": "JobComplete",
            "numberRecordsProcessed": 100
        }
    )

    status = await sf_batch_client.get_job_status("7500000001", mock_creds)
    assert status["state"] == "JobComplete"
    assert status["numberRecordsProcessed"] == 100


@pytest.mark.asyncio
@respx.mock
async def test_get_job_results_with_locator(mock_creds):
    respx.get("https://company.my.salesforce.com/services/data/v60.0/jobs/query/7500000001/results").respond(
        200,
        text="Id,Name\n001,Alpha\n",
        headers={"Sforce-Locator": "next_locator_456"}
    )

    csv_data, locator = await sf_batch_client.get_job_results("7500000001", mock_creds)
    assert "Alpha" in csv_data
    assert locator == "next_locator_456"


@pytest.mark.asyncio
@respx.mock
async def test_abort_job(mock_creds):
    respx.patch("https://company.my.salesforce.com/services/data/v60.0/jobs/query/7500000001").respond(
        200,
        json={
            "id": "7500000001",
            "state": "Aborted"
        }
    )

    res = await sf_batch_client.abort_job("7500000001", mock_creds)
    assert res["state"] == "Aborted"
