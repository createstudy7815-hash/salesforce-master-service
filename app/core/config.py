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

    # Resilience & DLQ Settings
    EXTERNAL_CALL_MAX_RETRIES: int = 3
    EXTERNAL_CALL_RETRY_DELAYS: List[float] = [0.1, 0.2, 0.4]
    EXTERNAL_CALL_JITTER: bool = True
    DLQ_PAYLOAD_MAX_BYTES: int = 10000

    # HMAC Authentication Settings
    HMAC_ENABLED: bool = True
    HMAC_COORDINATOR_CLIENT_ID: str = "coordinator"
    HMAC_ENGINEER_CLIENT_ID: str = "engineer"
    HMAC_SECRET_KEY_CORE: str = "coordinator-secret-key-sf-master"
    HMAC_SECRET_KEY_ENGINEER: str = "engineer-secret-key-sf-master"
    HMAC_SIGNATURE_MAX_AGE: int = 300  # 5 minutes in seconds

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v.lower()


settings = Settings()
