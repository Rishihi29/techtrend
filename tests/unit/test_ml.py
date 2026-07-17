"""ML modules: forecasting mechanics and anomaly ensemble behaviour."""

import numpy as np
import polars as pl

from techtrend.ml.registry import make_regressor


def test_regressor_factory_returns_working_model():
    model, flavour = make_regressor()
    x = np.arange(400, dtype=float).reshape(-1, 1)
    y = 2 * x.ravel() + 1
    model.fit(x, y)
    # in-range prediction: tree ensembles interpolate, they don't extrapolate
    pred = model.predict(np.array([[100.0]]))[0]
    assert flavour in ("lightgbm", "sklearn_hgb")
    assert 150 < pred < 250  # true value 201, leaf-width tolerance


def test_forecast_features_have_no_target_leakage():
    from techtrend.ml.forecasting import FEATURES

    # the raw target must never appear as its own feature
    assert "price" not in FEATURES
    assert all(f != "sales_velocity" for f in FEATURES)


def test_anomaly_alert_budget_caps_volume(isolated_lake, monkeypatch):
    """601 alerts from 45k rows locally; here: budget must bound the flags."""
    import techtrend.ml.anomaly as anomaly_mod

    rng = np.random.default_rng(7)
    n = 2000
    base = rng.normal(0, 1, n)
    base[:100] = rng.normal(0, 40, 100)  # inject shocks
    df = pl.DataFrame(
        {
            "product_id": rng.integers(1, 20, n),
            "observed_date": pl.date_range(
                pl.date(2026, 1, 1), pl.date(2026, 1, 1), eager=True
            ).extend_constant(pl.date(2026, 1, 1), n - 1),
            "price": rng.uniform(10, 100, n),
            "price_pct_change": base,
            "price_std_7": rng.uniform(0.1, 5, n),
            "discount_percentage": rng.uniform(0, 30, n),
            "sales_velocity": rng.uniform(0, 10, n),
        }
    )
    from techtrend.common import lake_io

    lake_io.write_parquet(df, "gold", "features", "product_daily_features.parquet")
    out = anomaly_mod.detect(contamination=0.005)
    budget = int(n * anomaly_mod.ALERT_BUDGET) + int(n * 0.005) + 5
    assert 0 < out.height <= budget
    assert set(out.get_column("anomaly_type").unique().to_list()) <= {
        "price_shock",
        "contextual",
        "price_shock_multivariate",
    }
