import pytest
import respx
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.schemas.auth import SalesforceCredentials
from app.services.sf_auth import SalesforceAuthClient


@pytest.fixture
def rsa_private_key_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")


@pytest.mark.asyncio
async def test_get_access_token_password_flow():
    client = SalesforceAuthClient()
    creds = SalesforceCredentials(
        login_url="https://test.salesforce.com",
        client_id="consumer_key_123",
        client_secret="consumer_secret_456",
        username="integration@example.com",
        password="my_password",
        security_token="my_token"
    )

    with respx.mock(base_url="https://test.salesforce.com") as respx_mock:
        token_route = respx_mock.post("/services/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "00Dtest_token_abc",
                    "instance_url": "https://custom-domain.my.salesforce.com",
                    "id": "https://test.salesforce.com/id/00DOrg12345/005User12345",
                    "token_type": "Bearer"
                }
            )
        )

        # 1st call: hits endpoint
        token_resp = await client.get_access_token(creds)
        assert token_resp.access_token == "00Dtest_token_abc"
        assert token_resp.instance_url == "https://custom-domain.my.salesforce.com"
        assert token_route.call_count == 1

        # 2nd call: hits in-memory cache, no new HTTP request
        cached_resp = await client.get_access_token(creds)
        assert cached_resp.access_token == "00Dtest_token_abc"
        assert token_route.call_count == 1

        # 3rd call with force_refresh: makes another HTTP request
        forced_resp = await client.get_access_token(creds, force_refresh=True)
        assert forced_resp.access_token == "00Dtest_token_abc"
        assert token_route.call_count == 2


@pytest.mark.asyncio
async def test_get_access_token_jwt_flow(rsa_private_key_pem):
    client = SalesforceAuthClient()
    creds = SalesforceCredentials(
        login_url="https://login.salesforce.com",
        client_id="jwt_client_id_789",
        username="jwt_user@example.com",
        private_key=rsa_private_key_pem,
        auth_flow="jwt_bearer"
    )

    with respx.mock(base_url="https://login.salesforce.com") as respx_mock:
        token_route = respx_mock.post("/services/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "00Djwt_token_xyz",
                    "instance_url": "https://prod-domain.my.salesforce.com",
                    "id": "https://login.salesforce.com/id/00DOrg999/005User999"
                }
            )
        )

        token_resp = await client.get_access_token(creds)
        assert token_resp.access_token == "00Djwt_token_xyz"
        assert token_route.call_count == 1


@pytest.mark.asyncio
async def test_validate_credentials_success():
    client = SalesforceAuthClient()
    creds = SalesforceCredentials(
        login_url="https://test.salesforce.com",
        client_id="consumer_key_123",
        username="integration@example.com",
        password="my_password"
    )

    with respx.mock(base_url="https://test.salesforce.com") as respx_mock:
        respx_mock.post("/services/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "token_123",
                    "instance_url": "https://test.salesforce.com",
                    "id": "https://test.salesforce.com/id/00DOrg12345/005User12345"
                }
            )
        )
        respx_mock.get("/id/00DOrg12345/005User12345").mock(
            return_value=httpx.Response(
                200,
                json={
                    "organization_id": "00DOrg12345",
                    "user_id": "005User12345",
                    "username": "integration@example.com"
                }
            )
        )

        result = await client.validate_credentials(creds)
        assert result.valid is True
        assert result.organization_id == "00DOrg12345"
        assert result.user_id == "005User12345"
        assert "successfully verified" in result.message


@pytest.mark.asyncio
async def test_validate_credentials_invalid():
    client = SalesforceAuthClient()
    creds = SalesforceCredentials(
        login_url="https://test.salesforce.com",
        client_id="invalid_client",
        username="bad_user@example.com",
        password="bad_password"
    )

    with respx.mock(base_url="https://test.salesforce.com") as respx_mock:
        respx_mock.post("/services/oauth2/token").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "authentication failure"
                }
            )
        )

        result = await client.validate_credentials(creds)
        assert result.valid is False
        assert "invalid_grant" in result.error_detail
