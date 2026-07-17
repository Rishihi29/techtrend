"""Data contracts (Pandera) enforced at the raw -> bronze boundary.

A record that violates its contract never reaches bronze: it is routed to
the quarantine area with a machine-readable failure reason. Contracts are
versioned with the code, so schema evolution is a reviewed change.
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl


class ProductContract(pa.DataFrameModel):
    product_id: int = pa.Field(gt=0, unique=True)
    name: str = pa.Field(str_length={"min_value": 1})
    category: str
    subcategory: str = pa.Field(nullable=True)
    brand: str = pa.Field(nullable=True)
    base_price: float = pa.Field(gt=0)
    base_rating: float = pa.Field(ge=0, le=5)
    image_url: str = pa.Field(nullable=True)

    class Config:
        strict = "filter"  # drop unexpected columns rather than failing the batch
        coerce = True


class PriceObservationContract(pa.DataFrameModel):
    fact_id: int = pa.Field(gt=0, unique=True)
    product_id: int = pa.Field(gt=0)
    time_id: int = pa.Field(gt=0)
    price: float = pa.Field(gt=0)
    original_price: float = pa.Field(gt=0, nullable=True)
    discount_percentage: float = pa.Field(ge=0, le=95)
    availability: str = pa.Field(isin=["In Stock", "Low Stock", "Out of Stock", "Pre-Order"])
    stock_level: int = pa.Field(ge=0)
    rating: float = pa.Field(ge=0, le=5, nullable=True)
    review_count: int = pa.Field(ge=0)
    sales_velocity: float = pa.Field(ge=0)
    is_trending: bool

    class Config:
        strict = "filter"
        coerce = True


def validate_split(
    df: pl.DataFrame, contract: type[pa.DataFrameModel]
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Validate a frame row-wise: returns ``(valid, rejected)``.

    Rejected rows carry a ``_dq_reason`` column so quarantined data is
    diagnosable, never a mystery.
    """
    try:
        valid = contract.validate(df, lazy=True)
        return pl.DataFrame(valid), df.head(0).with_columns(pl.lit("").alias("_dq_reason"))
    except pa.errors.SchemaErrors as err:
        failures = err.failure_cases
        # failure_cases is a polars frame with an `index` column for row-level checks
        bad_idx: set[int] = set()
        reasons: dict[int, str] = {}
        if "index" in failures.columns:
            for row in failures.iter_rows(named=True):
                idx = row.get("index")
                if idx is not None:
                    bad_idx.add(idx)
                    reasons.setdefault(idx, str(row.get("check")))
        if not bad_idx:
            # schema-level failure (e.g. missing column): reject the batch
            return df.head(0), df.with_columns(pl.lit(str(err)).alias("_dq_reason"))
        idx_col = pl.int_range(0, df.height).alias("_row_idx")
        with_idx = df.with_columns(idx_col)
        rejected = (
            with_idx.filter(pl.col("_row_idx").is_in(list(bad_idx)))
            .with_columns(
                pl.col("_row_idx")
                .map_elements(lambda i: reasons.get(i, "contract_violation"), return_dtype=pl.Utf8)
                .alias("_dq_reason")
            )
            .drop("_row_idx")
        )
        valid_df = with_idx.filter(~pl.col("_row_idx").is_in(list(bad_idx))).drop("_row_idx")
        valid_df = pl.DataFrame(contract.validate(valid_df))
        return valid_df, rejected
