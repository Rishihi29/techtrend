"""Ingestion primitives: idempotency, manifests, watermarks."""

import polars as pl

from techtrend.ingestion.base import get_watermark, land_raw, set_watermark
from techtrend.ingestion.retail_catalog import _rebase_dates


class TestLandings:
    def test_manifest_captures_rows_and_schema(self, isolated_lake):
        df = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        m = land_raw(df, source="test", dataset="d", load_date="2026-01-01")
        assert m.rows == 2
        assert len(m.schema_hash) == 16

    def test_reland_same_partition_is_idempotent(self, isolated_lake):
        df = pl.DataFrame({"a": [1]})
        land_raw(df, source="test", dataset="d", load_date="2026-01-01")
        land_raw(df, source="test", dataset="d", load_date="2026-01-01")
        landed = pl.read_parquet(str(isolated_lake / "lake/raw/test/dt=2026-01-01/d.parquet"))
        assert landed.height == 1  # overwrite, not append


class TestWatermarks:
    def test_roundtrip_and_isolation(self, isolated_lake, monkeypatch):
        monkeypatch.chdir(isolated_lake)
        assert get_watermark("src_a") is None
        set_watermark("src_a", "2026-01-01T00:00:00Z")
        assert get_watermark("src_a") == "2026-01-01T00:00:00Z"
        assert get_watermark("src_b") is None


def test_fixture_rebase_ends_yesterday():
    df = pl.DataFrame({"time_id": [1, 2], "full_date": ["2024-01-01", "2024-01-02"]})
    out = _rebase_dates(df)
    from datetime import date, timedelta

    assert max(out.get_column("full_date").to_list()) == str(date.today() - timedelta(days=1))
