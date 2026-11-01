from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Credentials are accepted only from environment/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groww_api_key: SecretStr | None = Field(default=None, repr=False)
    groww_api_secret: SecretStr | None = Field(default=None, repr=False)
    groww_access_token: SecretStr | None = Field(default=None, repr=False)
    algotrd_data_root: Path = Path("data")
    groww_timeout_seconds: float = 30.0
    groww_rate_limit_per_second: float = 2.0
    groww_max_retries: int = 4

    @property
    def manifest_path(self) -> Path:
        return self.algotrd_data_root / "manifests" / "ingestion.sqlite3"
