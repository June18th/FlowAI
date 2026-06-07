from __future__ import annotations

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _project_root = Path(__file__).resolve().parent.parent.parent
    model_config = SettingsConfigDict(
        env_file=str(_project_root / ".env"),
        env_file_encoding="utf-8",
        env_prefix="FLOWAGENT_",
        extra="ignore",
    )

    # Server
    server_port: int = 8084

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "flowagent"
    mysql_username: str = "root"
    mysql_password: str = "KnowHub2025"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6380
    redis_password: str = "KnowHub2025"
    redis_db: int = 0

    # MinIO
    minio_endpoint: str = "http://localhost:9002"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "KnowHub2025"
    minio_bucket_name: str = "flowagent"
    minio_public_url: str = "http://localhost:9002"

    # Auth
    jwt_secret: str = ""
    access_token_expiration_minutes: int = 120
    refresh_token_expiration_hours: int = 168
    default_username: str = "admin"
    default_password: str = "admin123"

    # Skills
    skills_path: str = "skills"

    # Durable execution
    durable_auto_resume: bool = False
    durable_orphan_threshold_seconds: int = 60
    durable_scan_interval_seconds: int = 30

    # OpenTelemetry
    otel_enabled: bool = True
    otel_service_name: str = "flowagent"
    otel_environment: str = "development"
    otel_exporter_otlp_endpoint: str = ""
    otel_console_export: bool = False
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+asyncmy://{self.mysql_username}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        base = f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
        if self.redis_password:
            base = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return base


settings = Settings()

# Auto-generate JWT secret for local dev
if not settings.jwt_secret:
    settings.jwt_secret = secrets.token_hex(32)
