"""Shared fixtures. Tests run against an isolated temp lake + warehouse so
they never touch developer data and are safe to run in parallel with CI."""

from __future__ import annotations

import polars as pl
import pytest


@pytest.fixture
def sample_products() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "product_id": [1, 2, 3],
            "name": [
                "Womens Teva Hurricane Sandals",
                "Buck 110 Folding Knife",
                "Mountain Classic Cordura Pack",
            ],
            "category": ["Fashion", "Fashion", "Fashion"],
            "subcategory": ["['Grey/White', 'Navy']", None, "['Camo']"],
            "brand": ["Generic", "Generic", "Generic"],
            "base_price": [59.95, 44.99, 79.0],
            "base_rating": [4.5, 4.8, 4.6],
            "image_url": ["https://example.com/1.jpg"] * 3,
        }
    )


@pytest.fixture
def isolated_lake(tmp_path, monkeypatch):
    """Point the platform at a throwaway lake/warehouse for the test."""
    from techtrend.config import settings as settings_mod

    monkeypatch.setenv("TECHTREND_LAKE_ROOT", str(tmp_path / "lake"))
    monkeypatch.setenv("TECHTREND_DUCKDB_PATH", str(tmp_path / "wh.duckdb"))
    settings_mod.get_settings.cache_clear()
    yield tmp_path
    settings_mod.get_settings.cache_clear()
