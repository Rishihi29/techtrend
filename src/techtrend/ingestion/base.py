"""Ingestion primitives: raw landings, manifests, and watermark state.

Contracts every connector must honour:

* Landings are **immutable** and keyed by ``raw/{source}/dt={load_date}/``,
  so re-running a load for the same logical date overwrites that partition
  and nothing else (idempotency by construction).
* Every landing writes a **manifest** capturing row counts, schema hash,
  and extraction parameters -- the audit trail a production platform needs.
* Incremental connectors persist a **high watermark** so each run pulls
  only deltas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from techtrend.common.lake_io import lake_path, write_parquet
from techtrend.common.logging import get_logger
from techtrend.config.settings import get_settings

log = get_logger(__name__)


@dataclass(frozen=True)
class LandingManifest:
    source: str
    dataset: str
    load_date: str
    rows: int
    schema_hash: str
    extracted_at: str
    params: dict[str, str]


def schema_fingerprint(df: pl.DataFrame) -> str:
    payload = json.dumps({c: str(t) for c, t in df.schema.items()}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def land_raw(
    df: pl.DataFrame,
    *,
    source: str,
    dataset: str,
    load_date: str,
    params: dict[str, str] | None = None,
) -> LandingManifest:
    """Write one immutable raw landing plus its manifest."""
    write_parquet(df, "raw", source, f"dt={load_date}", f"{dataset}.parquet")
    manifest = LandingManifest(
        source=source,
        dataset=dataset,
        load_date=load_date,
        rows=df.height,
        schema_hash=schema_fingerprint(df),
        extracted_at=datetime.now(UTC).isoformat(),
        params=params or {},
    )
    manifest_path = lake_path("raw", source, f"dt={load_date}", f"{dataset}.manifest.json")
    if not manifest_path.startswith("s3://"):
        Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(manifest_path).write_text(json.dumps(asdict(manifest), indent=2))
    log.info("raw_landing", **asdict(manifest))
    return manifest


# --------------------------------------------------------------------------
# Watermark state (small JSON file locally; the Postgres `ingestion_state`
# table in the Docker stack -- interface is identical either way).
# --------------------------------------------------------------------------
def _state_path() -> Path:
    settings = get_settings()
    return settings.local_dir("data", "state") / "ingestion_state.json"


def get_watermark(source: str) -> str | None:
    p = _state_path()
    if not p.exists():
        return None
    return json.loads(p.read_text()).get(source)


def set_watermark(source: str, value: str) -> None:
    p = _state_path()
    state = json.loads(p.read_text()) if p.exists() else {}
    state[source] = value
    p.write_text(json.dumps(state, indent=2))
    log.info("watermark_advanced", source=source, watermark=value)
