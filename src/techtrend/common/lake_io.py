"""Object-store-agnostic lake IO.

All reads and writes to the medallion lake go through this module. The
lake root may be a local directory (dev/CI) or an s3:// bucket
(MinIO locally, S3/GCS/ADLS in the cloud) -- callers never know which.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from techtrend.common.logging import get_logger
from techtrend.config.settings import get_settings

log = get_logger(__name__)

LAYERS = ("raw", "bronze", "silver", "gold")


def lake_path(layer: str, *parts: str) -> str:
    if layer not in LAYERS:
        raise ValueError(f"unknown lake layer {layer!r}; expected one of {LAYERS}")
    settings = get_settings()
    root = settings.lake_root.rstrip("/")
    return "/".join([root, layer, *parts])


def write_parquet(df: pl.DataFrame, layer: str, *parts: str) -> str:
    """Write a Parquet object; local parents are created automatically."""
    path = lake_path(layer, *parts)
    settings = get_settings()
    if not path.startswith("s3://"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path, compression="zstd")
    else:
        df.write_parquet(path, compression="zstd", storage_options=settings.storage_options)
    log.info("lake_write", layer=layer, path=path, rows=df.height)
    return path


def read_parquet(layer: str, *parts: str) -> pl.DataFrame:
    path = lake_path(layer, *parts)
    settings = get_settings()
    if path.startswith("s3://"):
        return pl.read_parquet(path, storage_options=settings.storage_options)
    return pl.read_parquet(path)


def scan_parquet(layer: str, *parts: str) -> pl.LazyFrame:
    """Lazy scan enabling predicate/projection pushdown into Parquet."""
    path = lake_path(layer, *parts)
    settings = get_settings()
    if path.startswith("s3://"):
        return pl.scan_parquet(path, storage_options=settings.storage_options)
    return pl.scan_parquet(path)
