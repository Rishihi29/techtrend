"""Centralised, environment-driven configuration (12-factor).

Every deployable component reads configuration exclusively from this
module. No credential, path, or endpoint is ever hardcoded elsewhere.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TECHTREND_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["local", "docker", "ci", "prod"] = "local"

    # lake -----------------------------------------------------------------
    # Local path by default; set to s3://techtrend-lake in Docker/cloud.
    lake_root: str = "data/lake"
    s3_endpoint_url: str | None = None  # e.g. http://minio:9000
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # warehouse --------------------------------------------------------------
    warehouse_backend: Literal["duckdb", "postgres"] = "duckdb"
    duckdb_path: str = "data/warehouse/techtrend.duckdb"
    postgres_dsn: str = "postgresql://techtrend:techtrend@localhost:5432/techtrend"

    # ingestion ---------------------------------------------------------------
    open_prices_base_url: str = "https://prices.openfoodfacts.org/api/v1"
    open_prices_page_size: int = 100
    open_prices_max_pages: int = 10
    ingestion_offline: bool = True  # offline demo mode uses bundled samples

    # ml ----------------------------------------------------------------------
    mlflow_tracking_uri: str | None = None  # e.g. http://mlflow:5000
    forecast_horizon_days: int = 14

    # api ---------------------------------------------------------------------
    api_title: str = "TechTrend Enterprise Data Platform API"
    api_page_size_max: int = 200

    @property
    def storage_options(self) -> dict[str, str] | None:
        """fsspec/object-store credentials for s3:// lake roots."""
        if not self.lake_root.startswith("s3://"):
            return None
        opts: dict[str, str] = {}
        if self.s3_access_key:
            opts["aws_access_key_id"] = self.s3_access_key
        if self.s3_secret_key:
            opts["aws_secret_access_key"] = self.s3_secret_key
        if self.s3_endpoint_url:
            opts["endpoint_url"] = self.s3_endpoint_url
        return opts

    def local_dir(self, *parts: str) -> Path:
        p = Path(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
