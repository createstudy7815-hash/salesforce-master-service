from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # App Metadata
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./salesforce_master.db"
    DATABASE_POOL_SIZE: int = 10

    # Salesforce Default API Settings
    SF_LOGIN_URL: str = "https://login.salesforce.com"
    SF_CLIENT_ID: Optional[str] = None
    SF_CLIENT_SECRET: Optional[str] = None
    SF_JWT_KEY_PATH: Optional[str] = None
    SF_API_VERSION: str = "v60.0"
    SF_TIMEOUT_SECONDS: int = 60
    SF_BULK_POLL_INTERVAL_SECONDS: int = 5
    SF_BULK_MAX_WAIT_MINUTES: int = 30
    SF_SUPPORTED_OBJECTS: List[str] = [
        "Account",
        "Contact",
        "Opportunity",
        "Lead",
        "Case",
        "Task",
        "Event",
        "Campaign",
        "User"
    ]

    # MinIO / S3 Storage Settings
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_BUCKET: str = "salesforce-data"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False

    # Resilience & Retries
    EXTERNAL_CALL_MAX_RETRIES: int = 3
    EXTERNAL_CALL_RETRY_DELAYS: List[int] = [2, 5, 10]
    EXTERNAL_CALL_JITTER: bool = True
    DLQ_PAYLOAD_MAX_BYTES: int = 65536

    # HMAC Authentication
    HMAC_ENABLED: bool = False
    HMAC_SECRET_KEY_CORE: str = "dev_coordinator_secret_key_32bytes_min"
    HMAC_SECRET_KEY_ENGINEER: str = "dev_engineer_secret_key_32bytes_min"
    HMAC_SIGNATURE_MAX_AGE: int = 300

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v.lower()


settings = Settings()
