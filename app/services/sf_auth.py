import time
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
import jwt
import httpx

from app.schemas.auth import SalesforceCredentials, TokenResponse, CredentialValidationResponse

logger = logging.getLogger(__name__)


class CachedToken:
    def __init__(self, token_response: TokenResponse, expires_in_seconds: int = 7200):
        self.token_response = token_response
        self.cached_at = time.time()
        # Salesforce OAuth tokens typically expire in 2 hours.
        # We refresh if within 5 minutes (300 seconds) of expiry.
        self.expires_at = self.cached_at + expires_in_seconds - 300

    def is_valid(self) -> bool:
        return time.time() < self.expires_at


class SalesforceAuthClient:
    """
    Salesforce OAuth 2.0 Client supporting:
    - OAuth 2.0 JWT Bearer flow (RFC 7523)
    - OAuth 2.0 Username-Password flow
    - In-memory token caching with near-expiry buffer
    - Lightweight credential validation
    """

    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds
        self._token_cache: Dict[str, CachedToken] = {}

    def _get_cache_key(self, creds: SalesforceCredentials) -> str:
        """Derive unique in-memory cache key from non-sensitive parameters."""
        raw_key = f"{creds.login_url.rstrip('/')}:{creds.client_id}:{creds.username}:{creds.auth_flow}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def clear_cache(self) -> None:
        """Clear all cached OAuth tokens."""
        self._token_cache.clear()

    async def get_access_token(self, creds: SalesforceCredentials, force_refresh: bool = False) -> TokenResponse:
        """
        Obtain an OAuth access token, reusing cached token if valid.
        Credentials are never logged or persisted.
        """
        cache_key = self._get_cache_key(creds)
        if not force_refresh and cache_key in self._token_cache:
            cached = self._token_cache[cache_key]
            if cached.is_valid():
                logger.debug(f"Using cached Salesforce access token for user {creds.username}")
                return cached.token_response

        token_endpoint = f"{creds.login_url.rstrip('/')}/services/oauth2/token"

        if creds.auth_flow == "jwt_bearer":
            payload_data = self._build_jwt_request(creds)
        else:
            payload_data = self._build_password_request(creds)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(token_endpoint, data=payload_data)
            resp.raise_for_status()
            data = resp.json()
            token_response = TokenResponse(
                access_token=data["access_token"],
                instance_url=data["instance_url"],
                id=data.get("id"),
                token_type=data.get("token_type", "Bearer"),
                issued_at=data.get("issued_at"),
                signature=data.get("signature"),
            )

        self._token_cache[cache_key] = CachedToken(token_response)
        return token_response

    def _build_jwt_request(self, creds: SalesforceCredentials) -> Dict[str, str]:
        """Construct JWT Bearer assertion."""
        now = int(time.time())
        claims = {
            "iss": creds.client_id,
            "sub": creds.username,
            "aud": creds.login_url.rstrip("/"),
            "exp": now + 300  # Valid for 5 minutes
        }

        try:
            assertion = jwt.encode(
                claims,
                creds.private_key,
                algorithm="RS256"
            )
        except Exception as exc:
            raise ValueError(f"Failed to sign JWT with provided private key: {exc}") from exc

        return {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion
        }

    def _build_password_request(self, creds: SalesforceCredentials) -> Dict[str, str]:
        """Construct Username-Password flow body."""
        full_password = creds.password or ""
        if creds.security_token:
            full_password += creds.security_token

        data = {
            "grant_type": "password",
            "client_id": creds.client_id,
            "username": creds.username,
            "password": full_password
        }
        if creds.client_secret:
            data["client_secret"] = creds.client_secret

        return data

    async def validate_credentials(self, creds: SalesforceCredentials) -> CredentialValidationResponse:
        """
        Validate credentials by requesting a token and fetching user identity.
        Does NOT create any scan or job in the database.
        """
        try:
            token_resp = await self.get_access_token(creds, force_refresh=True)
            org_id, user_id = self._parse_identity_url(token_resp.id_url)

            # Confirm token reachability with identity endpoint if available
            if token_resp.id_url:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    ident_resp = await client.get(
                        token_resp.id_url,
                        headers={"Authorization": f"Bearer {token_resp.access_token}"}
                    )
                    if ident_resp.status_code == 200:
                        ident_data = ident_resp.json()
                        org_id = ident_data.get("organization_id", org_id)
                        user_id = ident_data.get("user_id", user_id)

            return CredentialValidationResponse(
                valid=True,
                organization_id=org_id,
                user_id=user_id,
                username=creds.username,
                instance_url=token_resp.instance_url,
                auth_flow=creds.auth_flow,
                message="Salesforce credentials successfully verified."
            )

        except httpx.HTTPStatusError as exc:
            logger.warning(f"Salesforce credential verification failed: HTTP {exc.response.status_code}")
            try:
                err_json = exc.response.json()
                detail = f"{err_json.get('error', '')}: {err_json.get('error_description', '')}".strip(": ")
            except Exception:
                detail = exc.response.text
            return CredentialValidationResponse(
                valid=False,
                username=creds.username,
                auth_flow=creds.auth_flow,
                message="Salesforce authentication failed.",
                error_detail=detail or f"HTTP {exc.response.status_code}"
            )

        except Exception as exc:
            logger.error(f"Unexpected error validating credentials: {exc}")
            return CredentialValidationResponse(
                valid=False,
                username=creds.username,
                auth_flow=creds.auth_flow,
                message="Could not connect to Salesforce.",
                error_detail=str(exc)
            )

    @staticmethod
    def _parse_identity_url(id_url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """Extract (org_id, user_id) from standard Salesforce identity URL (https://login.salesforce.com/id/00D.../005...)."""
        if not id_url:
            return None, None
        parts = id_url.rstrip("/").split("/")
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return None, None


# Global singleton instance
sf_auth_client = SalesforceAuthClient()
