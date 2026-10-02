from typing import Optional
from pydantic import BaseModel, Field, model_validator


class SalesforceCredentials(BaseModel):
    login_url: str = Field(default="https://login.salesforce.com", description="Salesforce login endpoint")
    client_id: str = Field(..., description="Connected App Consumer Key")
    client_secret: Optional[str] = Field(None, description="Connected App Consumer Secret (for password flow)")
    username: str = Field(..., description="Salesforce username")
    password: Optional[str] = Field(None, description="Salesforce password (for password flow)")
    security_token: Optional[str] = Field(None, description="Salesforce security token (appended to password)")
    private_key: Optional[str] = Field(None, description="RSA Private Key in PEM format (for JWT Bearer flow)")
    auth_flow: Optional[str] = Field(None, description="Explicit auth flow: 'jwt_bearer' or 'password'")

    @model_validator(mode="after")
    def validate_flow_requirements(self) -> "SalesforceCredentials":
        # Auto-detect or validate required credentials
        if self.auth_flow == "jwt_bearer" or (self.auth_flow is None and self.private_key):
            if not self.private_key:
                raise ValueError("private_key is required for JWT Bearer authentication flow.")
            self.auth_flow = "jwt_bearer"
        elif self.auth_flow == "password" or (self.auth_flow is None and self.password):
            if not self.password:
                raise ValueError("password is required for Username-Password authentication flow.")
            self.auth_flow = "password"
        else:
            raise ValueError("Credentials must provide either private_key (JWT flow) or password (Password flow).")
        return self


class TokenResponse(BaseModel):
    access_token: str
    instance_url: str
    token_type: str = "Bearer"
    id_url: Optional[str] = Field(None, alias="id")
    issued_at: Optional[str] = None
    signature: Optional[str] = None


class CredentialValidationResponse(BaseModel):
    valid: bool
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    instance_url: Optional[str] = None
    auth_flow: Optional[str] = None
    message: str
    error_detail: Optional[str] = None
