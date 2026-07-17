"""Data-quality contracts and scoring."""

from datetime import date, timedelta

import polars as pl

from techtrend.quality.schemas import PriceObservationContract, validate_split
from techtrend.quality.score import compute


def _obs(**overrides) -> dict:
    base = {
        "fact_id": 1,
        "product_id": 1,
        "time_id": 1,
        "price": 10.0,
        "original_price": 12.0,
        "discount_percentage": 16.7,
        "availability": "In Stock",
        "stock_level": 5,
        "rating": 4.2,
        "review_count": 10,
        "sales_velocity": 1.0,
        "is_trending": True,
    }
    return {**base, **overrides}


class TestContractQuarantine:
    def test_bad_rows_quarantined_good_rows_pass(self):
        df = pl.DataFrame(
            [
                _obs(),
                _obs(fact_id=2, price=-5.0),  # invalid: negative price
                _obs(fact_id=3, availability="Maybe"),  # invalid: unknown enum
            ]
        )
        valid, rejected = validate_split(df, PriceObservationContract)
        assert valid.height == 1
        assert rejected.height == 2
        assert "_dq_reason" in rejected.columns

    def test_clean_batch_rejects_nothing(self):
        df = pl.DataFrame([_obs(), _obs(fact_id=2)])
        valid, rejected = validate_split(df, PriceObservationContract)
        assert (valid.height, rejected.height) == (2, 0)


class TestQualityScore:
    def _frame(self, observed: date) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "product_id": [1, 2],
                "observed_date": [observed, observed],
                "price": [10.0, 20.0],
                "original_price": [12.0, 25.0],
                "discount_percentage": [16.7, 20.0],
                "rating": [4.0, 4.5],
            }
        )

    def test_fresh_clean_data_scores_high(self):
        report = compute(self._frame(date.today()), rejected_rows=0)
        assert report.composite_score > 0.95
        assert report.uniqueness == 1.0

    def test_stale_data_degrades_freshness_only(self):
        report = compute(self._frame(date.today() - timedelta(days=60)))
        assert report.freshness == 0.0
        assert report.completeness == 1.0

    def test_inconsistent_pricing_detected(self):
        df = self._frame(date.today()).with_columns(pl.lit(5.0).alias("original_price"))
        report = compute(df)  # price > original_price
        assert report.consistency == 0.0
