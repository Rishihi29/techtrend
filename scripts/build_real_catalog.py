"""Real-dataset onboarding: Amazon product catalog (Bright Data sample export).

Source: github.com/luminati-io/Amazon-dataset-samples (1,000 real Amazon
listings — real titles, brands, categories, ratings, and CDN image URLs;
freely distributed as a promotional sample dataset).

This script produces `data/samples/kaggle_products.csv` in the platform's
existing product schema, so nothing downstream (bronze/silver/gold, dbt,
API) needs to change shape -- only the *content* becomes real.

Run once: `python scripts/build_real_catalog.py`
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAW = Path("data/amazon_raw/amazon-products.csv")
OUT = Path("data/samples/kaggle_products.csv")


def clean_price(v) -> float | None:
    if pd.isna(v):
        return None
    s = str(v).strip().strip('"').replace(",", "")
    try:
        f = float(s)
        return round(f, 2) if f > 0 else None
    except ValueError:
        return None


def parse_categories(raw: str) -> list[str]:
    if not isinstance(raw, str):
        return []
    try:
        return [c for c in json.loads(raw) if isinstance(c, str) and c.strip()]
    except (json.JSONDecodeError, TypeError):
        return []


def main() -> None:
    df = pd.read_csv(RAW)

    price = df["final_price"].apply(clean_price)
    price = price.fillna(df["initial_price"].apply(clean_price))

    cats = df["categories"].apply(parse_categories)
    # top_category = broad department (Electronics, Home & Kitchen, ...);
    # subcategory = the most specific real node the source gave us.
    top_category = cats.apply(lambda c: c[0] if c else "General Merchandise")
    subcategory = cats.apply(lambda c: c[-1] if len(c) > 1 else (c[0] if c else "General"))

    brand = df["brand"].fillna(df["manufacturer"]).fillna("Unbranded").astype(str).str.strip()
    brand = brand.replace({"nan": "Unbranded", "": "Unbranded"})

    out = pd.DataFrame(
        {
            "product_id": range(1, len(df) + 1),
            "name": df["title"].astype(str).str.strip(),
            "category": top_category,
            "subcategory": subcategory,
            "brand": brand,
            "base_price": price.fillna(price.median()).round(2),
            "base_rating": df["rating"].fillna(df["rating"].median()).clip(1, 5).round(1),
            "image_url": df["image_url"],
            # lineage: real Amazon identifiers, kept for traceability / provenance
            "source_asin": df["asin"],
            "source_url": df["url"],
        }
    )

    # a handful of image URLs are blank; those fall back cleanly downstream
    # (the console already handles a missing image with a graceful placeholder)
    out = out.dropna(subset=["name", "base_price"]).reset_index(drop=True)
    out["product_id"] = range(1, len(out) + 1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"wrote {len(out)} real products -> {OUT}")
    print("\ncategory distribution:")
    print(out["category"].value_counts().to_string())
    print(f"\nunique brands: {out['brand'].nunique()}")


if __name__ == "__main__":
    main()
