from unittest.mock import AsyncMock, patch
from app.schemas.auth import CredentialValidationResponse


def test_validate_credentials_api_success(client):
    mock_response = CredentialValidationResponse(
        valid=True,
        organization_id="00DTestOrg",
        user_id="005TestUser",
        username="admin@company.com",
        instance_url="https://company.my.salesforce.com",
        auth_flow="password",
        message="Salesforce credentials successfully verified."
    )

    with patch("app.api.v1.endpoints.credentials.sf_auth_client.validate_credentials", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = mock_response

        payload = {
            "login_url": "https://login.salesforce.com",
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "username": "admin@company.com",
            "password": "secret_password"
        }

        response = client.post("/api/validate-credentials", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["organization_id"] == "00DTestOrg"
        assert data["username"] == "admin@company.com"


def test_validate_credentials_api_failure(client):
    mock_response = CredentialValidationResponse(
        valid=False,
        username="bad@company.com",
        message="Salesforce authentication failed.",
        error_detail="invalid_grant: authentication failure"
    )

    with patch("app.api.v1.endpoints.credentials.sf_auth_client.validate_credentials", new_callable=AsyncMock) as mock_val:
        mock_val.return_value = mock_response

        payload = {
            "login_url": "https://login.salesforce.com",
            "client_id": "bad_client_id",
            "username": "bad@company.com",
            "password": "wrong_password"
        }

        response = client.post("/api/validate-credentials", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["message"] == "Salesforce authentication failed."

