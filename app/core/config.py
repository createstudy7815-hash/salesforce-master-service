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

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v.lower()


settings = Settings()
