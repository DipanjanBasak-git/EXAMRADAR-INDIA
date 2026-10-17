"""ExamRadar India - Core Configuration"""

import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "sqlite:///./examradar.db"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_debug: bool = False
    backend_secret_key: str = "change-this-to-a-random-secret-key-in-production"
    cors_origins: str = "chrome-extension://localhost,http://localhost:3000"

    # Discovery
    discovery_enabled: bool = True
    discovery_interval_minutes: int = 60
    discovery_max_concurrent: int = 3
    discovery_request_timeout: int = 30
    discovery_respect_robots_txt: bool = True

    # Optional AI
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

    # Optional Search
    search_api_key: Optional[str] = None
    search_provider: str = "google"
    search_daily_limit: int = 100

    # Rate Limiting
    rate_limit_requests_per_minute: int = 60

    # Logging
    log_level: str = "INFO"
    log_file: str = "examradar.log"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
