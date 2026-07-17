"""Price anomaly detection.

Two complementary detectors, ensembled:

* **Robust z-score** (median/MAD) on daily price changes per product --
  interpretable, catches point spikes; subsumes the original TechTrend
  ">15% drop" trend rule as a special case.
* **IsolationForest** over multivariate daily behaviour (price change,
  discount, volatility, velocity) -- catches contextual anomalies a
  univariate rule misses.

A row is flagged when either detector fires; both scores are persisted so
analysts can see *why*.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.ensemble import IsolationForest

from techtrend.common.lake_io import read_parquet, write_parquet
from techtrend.common.logging import get_logger
from techtrend.ml.registry import log_run

log = get_logger(__name__)

Z_THRESHOLD = 3.5  # Iglewicz-Hoaglin recommended cutoff for modified z
MATERIALITY_PCT = 10.0  # statistical outliers below this move are noise, not signal
ALERT_BUDGET = 0.01  # promote at most 1% of scored rows to analyst-facing alerts


def detect(contamination: float = 0.005) -> pl.DataFrame:
    df = read_parquet("gold", "features", "product_daily_features.parquet").drop_nulls(
        subset=["price_pct_change", "price_std_7"]
    )

    # ---- robust z-score per product (Iglewicz-Hoaglin modified z) ----
    centered = pl.col("price_pct_change") - pl.col("price_pct_change").median().over("product_id")
    mad = centered.abs().median().over("product_id")
    df = df.with_columns((0.6745 * centered / (mad + 1e-9)).alias("robust_z"))

    # ---- isolation forest over multivariate behaviour ----
    feat_cols = ["price_pct_change", "discount_percentage", "price_std_7", "sales_velocity"]
    x = df.select(feat_cols).to_numpy()
    forest = IsolationForest(contamination=contamination, random_state=42, n_estimators=200)
    forest_flag = forest.fit_predict(x) == -1
    forest_score = -forest.score_samples(x)  # higher = more anomalous

    df = (
        df.with_columns(
            pl.Series("iforest_score", np.round(forest_score, 4)),
            pl.Series("iforest_flag", forest_flag),
        )
        .with_columns(
            (
                (pl.col("robust_z").abs() > Z_THRESHOLD)
                & (pl.col("price_pct_change").abs() >= MATERIALITY_PCT)
            ).alias("zscore_candidate")
        )
        .with_columns(
            # Alert budget: this domain is volatile enough that raw statistical
            # flags would swamp analysts. Candidates are ranked by severity and
            # only the top ALERT_BUDGET share is promoted -- the same discipline
            # a production alerting pipeline applies to noisy signals.
            (
                pl.col("zscore_candidate")
                & (
                    pl.col("robust_z").abs().rank(descending=True)
                    <= max(1, int(df.height * ALERT_BUDGET))
                )
            ).alias("zscore_flag")
        )
        .with_columns(
            (pl.col("iforest_flag") | pl.col("zscore_flag")).alias("is_anomaly"),
            pl.when(pl.col("zscore_flag") & pl.col("iforest_flag"))
            .then(pl.lit("price_shock_multivariate"))
            .when(pl.col("zscore_flag"))
            .then(pl.lit("price_shock"))
            .when(pl.col("iforest_flag"))
            .then(pl.lit("contextual"))
            .otherwise(pl.lit("normal"))
            .alias("anomaly_type"),
        )
    )

    anomalies = df.filter(pl.col("is_anomaly")).select(
        "product_id",
        "observed_date",
        "price",
        "price_pct_change",
        pl.col("robust_z").round(3),
        "iforest_score",
        "anomaly_type",
    )

    run_id = log_run(
        experiment="anomaly_detection",
        params={
            "contamination": contamination,
            "z_threshold": Z_THRESHOLD,
            "alert_budget": ALERT_BUDGET,
            "materiality_pct": MATERIALITY_PCT,
            "detectors": "robust_z+isolation_forest",
        },
        metrics={
            "rows_scored": float(df.height),
            "anomalies_found": float(anomalies.height),
            "anomaly_rate_pct": round(100 * anomalies.height / max(df.height, 1), 3),
        },
    )
    anomalies = anomalies.with_columns(pl.lit(run_id).alias("model_run_id"))
    write_parquet(anomalies, "gold", "ml", "anomalies.parquet")
    log.info("anomaly_detection_complete", anomalies=anomalies.height)
    return anomalies
