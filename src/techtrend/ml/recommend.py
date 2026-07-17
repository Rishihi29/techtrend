"""Product recommendations.

Content-based nearest-neighbour retrieval over the governed product
profile (price behaviour, discount posture, rating, velocity, category)
built in the gold layer. Chosen deliberately over collaborative filtering:
the platform observes *market* data, not per-user interactions, so
user-item matrix factorisation would be modelling noise. The design keeps
a clean seam -- ``top_k`` returns (product, score, reason) -- so an ALS
model can slot in when interaction data (e.g. Olist orders) is onboarded.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from techtrend.common.lake_io import read_parquet, write_parquet
from techtrend.common.logging import get_logger
from techtrend.ml.registry import log_run

log = get_logger(__name__)

NUMERIC = ["avg_price", "price_volatility", "avg_discount", "avg_rating", "avg_velocity"]


def build(top_k: int = 6) -> pl.DataFrame:
    segments = read_parquet("gold", "segments", "product_segments.parquet")

    x_num = StandardScaler().fit_transform(segments.select(NUMERIC).to_numpy())
    cats = segments.get_column("category").to_list()
    cat_onehot = np.array([[1.0 if c == u else 0.0 for u in sorted(set(cats))] for c in cats])
    x = np.hstack([x_num, cat_onehot * 2.0])  # same-category affinity boost

    nn = NearestNeighbors(n_neighbors=top_k + 1, metric="cosine").fit(x)
    dist, idx = nn.kneighbors(x)

    pids = segments.get_column("product_id").to_list()
    names = segments.get_column("segment_name").to_list()
    rows = []
    for i, pid in enumerate(pids):
        rank = 0
        for j, d in zip(idx[i], dist[i], strict=True):
            if pids[j] == pid:
                continue
            rank += 1
            rows.append(
                {
                    "product_id": pid,
                    "recommended_product_id": pids[j],
                    "rank": rank,
                    "similarity": round(float(1 - d), 4),
                    "reason": (
                        f"Similar {cats[j]} profile"
                        + (f" in the {names[j]} segment" if names[j] == names[i] else "")
                    ),
                }
            )
            if rank >= top_k:
                break

    recs = pl.DataFrame(rows)
    log_run(
        experiment="recommendations",
        params={
            "algorithm": "content_knn_cosine",
            "top_k": top_k,
            "features": ",".join(NUMERIC) + "+category",
        },
        metrics={
            "products_covered": float(segments.height),
            "avg_top1_similarity": float(
                recs.filter(pl.col("rank") == 1).get_column("similarity").mean() or 0  # type: ignore[arg-type]
            ),
        },
    )
    write_parquet(recs, "gold", "ml", "recommendations.parquet")
    log.info("recommendations_built", pairs=recs.height)
    return recs
