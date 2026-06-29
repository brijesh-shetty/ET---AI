"""Application configuration loaded from environment variables.

All runtime knobs live here. The frontend, ingest workers and API handlers
read settings through ``get_settings()`` which is memoised for the process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = Field(default="dev")
    log_level: str = Field(default="INFO")

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    data_root: str = Field(default="./data")

    allow_live_ingest: bool = Field(default=False)

    anthropic_api_key: str | None = Field(default=None)
    anthropic_synthesis_model: str = Field(default="claude-opus-4-8")
    anthropic_classifier_model: str = Field(default="claude-haiku-4-5-20251001")

    ais_stream_api_key: str | None = Field(default=None)
    ais_stream_url: str = Field(default="wss://stream.aisstream.io/v0/stream")

    gdelt_enabled: bool = Field(default=True)
    gdelt_base_url: str = Field(default="https://api.gdeltproject.org/api/v2")

    ppac_base_url: str = Field(default="https://www.ppac.gov.in")
    eia_api_key: str | None = Field(default=None)
    alpha_vantage_api_key: str | None = Field(default=None)
    world_bank_base_url: str = Field(default="https://api.worldbank.org/v2")

    ofac_sdn_url: str = Field(
        default="https://www.treasury.gov/ofac/downloads/sdn.xml"
    )
    un_sanctions_url: str = Field(
        default="https://scsanctions.un.org/resources/xml/en/consolidated.xml"
    )

    cache_ttl_seconds: int = Field(default=300)
    http_timeout_seconds: float = Field(default=20.0)

    @property
    def fixtures_path(self) -> Path:
        """Directory containing offline fixture JSON used when live ingest is off."""
        return (Path(self.data_root) / "fixtures").resolve()

    @property
    def snapshots_path(self) -> Path:
        """Directory for serialised snapshots produced by ingest workers."""
        return (Path(self.data_root) / "snapshots").resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached process-wide settings instance."""
    return Settings()
