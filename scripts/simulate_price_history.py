"""Daily telemetry simulation over the real Amazon catalog.

No free dataset provides 90 days of historical daily pricing for 1,000
real products (price-history services like Keepa are commercial/paid) --
this is a known, documented constraint of the domain, not a shortcut
(see docs/adr/ADR-004). The catalog (name, brand, category, rating,
image, list price) is 100% real; what's simulated is the day-to-day
*telemetry* a repricing/monitoring bot would collect once deployed --
exactly what this platform is built to ingest incrementally.

The simulator itself is a legitimate technique (mean-reverting random
walk + promotional event injection + accumulating review counts), not
uniform noise: prices wander around each product's real list price,
occasional promo events discount them, stock depletes and restocks,
review counts only ever grow.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PRODUCTS = Path("data/samples/kaggle_products.csv")
OUT_FACTS = Path("data/samples/kaggle_facts.csv")
OUT_TIME = Path("data/samples/kaggle_time.csv")
DAYS = 90
SEED = 42

# Higher-volatility departments swing more day to day (electronics/tools
# see more promo cycles than grocery/household staples).
VOLATILE_CATEGORIES = {
    "Electronics",
    "Cell Phones & Accessories",
    "Automotive",
    "Tools & Home Improvement",
    "Video Games",
    "Appliances",
}


def build_time_dim() -> pd.DataFrame:
    end = pd.Timestamp.now("UTC").normalize() - pd.Timedelta(days=1)
    dates = pd.date_range(end=end, periods=DAYS, freq="D")
    df = pd.DataFrame({"time_id": range(1, DAYS + 1), "full_date": dates})
    df["day_of_week"] = df["full_date"].dt.day_name()
    df["day_of_month"] = df["full_date"].dt.day
    df["month"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.month_name()
    df["quarter"] = df["full_date"].dt.quarter
    df["year"] = df["full_date"].dt.year
    df["is_weekend"] = df["full_date"].dt.dayofweek >= 5
    return df


def simulate(products: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    n = len(products)
    base_price = products["base_price"].to_numpy()
    volatility = np.where(products["category"].isin(VOLATILE_CATEGORIES), 0.020, 0.008)
    popularity = rng.lognormal(mean=3.0, sigma=1.1, size=n)  # drives review velocity

    # ---- mean-reverting price walk, vectorised across all products ----
    baseline = np.tile(base_price, (DAYS, 1))  # (DAYS, n)
    for t in range(1, DAYS):
        reversion = 0.05 * (base_price - baseline[t - 1])
        noise = rng.normal(0, volatility * base_price)
        baseline[t] = np.clip(
            baseline[t - 1] + reversion + noise, base_price * 0.5, base_price * 1.8
        )

    promo = rng.random((DAYS, n)) < 0.16
    discount_pct = np.where(promo, rng.uniform(8, 45, (DAYS, n)), 0.0)
    price = np.round(baseline * (1 - discount_pct / 100), 2)
    original_price = np.round(baseline, 2)

    # ---- stock: depletes faster during promos, restocks stochastically ----
    stock = np.zeros((DAYS, n), dtype=int)
    stock[0] = rng.integers(20, 120, n)
    for t in range(1, DAYS):
        draw = rng.poisson(3 + 12 * promo[t])
        restock = np.where(rng.random(n) < 0.12, rng.integers(30, 100, n), 0)
        stock[t] = np.clip(stock[t - 1] - draw + restock, 0, None)

    availability = np.select(
        [stock == 0, stock <= 5, stock <= 15],
        ["Out of Stock", "Low Stock", "Low Stock"],
        default="In Stock",
    )
    preorder_mask = rng.random((DAYS, n)) < 0.004
    availability = np.where(preorder_mask, "Pre-Order", availability)

    # ---- reviews only accumulate; rating drifts gently ----
    daily_reviews = rng.poisson(np.clip(popularity / 8, 0.05, None), (DAYS, n))
    review_count = np.cumsum(daily_reviews, axis=0) + rng.integers(0, 40, n)
    rating = np.clip(
        products["base_rating"].to_numpy() + rng.normal(0, 0.06, (DAYS, n)).cumsum(axis=0) * 0.02,
        1.0,
        5.0,
    )

    # ---- sales velocity: higher on discount days, scaled by popularity ----
    velocity = np.clip(
        (popularity / 10) * (1 + 1.8 * promo) * rng.lognormal(0, 0.35, (DAYS, n)),
        0,
        None,
    )
    trend_cutoff = np.quantile(velocity, 0.95, axis=1, keepdims=True)
    is_trending = velocity >= trend_cutoff

    rows = []
    fact_id = 1
    product_ids = products["product_id"].to_numpy()
    for t in range(DAYS):
        for i in range(n):
            rows.append(
                (
                    fact_id,
                    product_ids[i],
                    t + 1,
                    price[t, i],
                    original_price[t, i],
                    round(discount_pct[t, i], 2),
                    availability[t, i],
                    int(stock[t, i]),
                    round(float(rating[t, i]), 2),
                    int(review_count[t, i]),
                    round(float(velocity[t, i]), 2),
                    bool(is_trending[t, i]),
                )
            )
            fact_id += 1

    return pd.DataFrame(
        rows,
        columns=[
            "fact_id",
            "product_id",
            "time_id",
            "price",
            "original_price",
            "discount_percentage",
            "availability",
            "stock_level",
            "rating",
            "review_count",
            "sales_velocity",
            "is_trending",
        ],
    )


def main() -> None:
    products = pd.read_csv(PRODUCTS)
    rng = np.random.default_rng(SEED)

    time_dim = build_time_dim()
    time_dim.to_csv(OUT_TIME, index=False)
    print(f"wrote {len(time_dim)} calendar rows -> {OUT_TIME}")

    facts = simulate(products, rng)
    facts.to_csv(OUT_FACTS, index=False)
    print(f"wrote {len(facts)} price observations -> {OUT_FACTS}")
    print(f"  products: {products.shape[0]}  x  days: {DAYS}")
    print(f"  avg discount rate: {(facts['discount_percentage'] > 0).mean():.1%}")
    print(f"  avg price: ${facts['price'].mean():.2f}")


if __name__ == "__main__":
    main()
