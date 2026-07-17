"""Warehouse access layer.

Routers never touch SQL or connections directly; they call typed
repository functions. The backend (DuckDB file locally / in the demo,
Postgres in the Docker stack) is selected by configuration alone.
All SQL is parameterised -- string interpolation of user input is banned.
"""

from __future__ import annotations

import threading
from typing import Any

import duckdb

from techtrend.config.settings import get_settings

_lock = threading.Lock()
_conn: duckdb.DuckDBPyConnection | None = None


def _connect() -> duckdb.DuckDBPyConnection:
    global _conn
    settings = get_settings()
    if settings.warehouse_backend == "postgres":
        # DuckDB's postgres extension gives us one query interface for both
        # backends -- the repository code is byte-identical either way.
        conn = duckdb.connect()
        conn.execute("INSTALL postgres; LOAD postgres;")
        conn.execute(f"ATTACH '{settings.postgres_dsn}' AS pg (TYPE postgres, READ_ONLY);")
        conn.execute("USE pg.analytics;")
        return conn
    if _conn is None:
        _conn = duckdb.connect(settings.duckdb_path, read_only=True)
    return _conn


def query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    with _lock:
        cur = _connect().execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def scalar(sql: str, params: list[Any] | None = None) -> Any:
    rows = query(sql, params)
    return next(iter(rows[0].values())) if rows else None


# --------------------------------------------------------------------------
# Product catalog
# --------------------------------------------------------------------------
SORTABLE = {
    "avg_price": "avg_price",
    "avg_rating": "avg_rating",
    "avg_discount": "avg_discount",
    "price_volatility": "price_volatility",
    "total_reviews": "total_reviews",
    "product_name": "product_name",
}


def list_products(
    *,
    page: int,
    page_size: int,
    category: str | None,
    brand: str | None,
    search: str | None,
    min_price: float | None,
    max_price: float | None,
    min_rating: float | None,
    sort_by: str,
    descending: bool,
) -> tuple[list[dict], int]:
    clauses, params = ["1=1"], []
    if category:
        clauses.append("p.category = ?")
        params.append(category)
    if brand:
        clauses.append("p.brand = ?")
        params.append(brand)
    if search:
        clauses.append("(lower(p.product_name) LIKE ? OR lower(p.brand) LIKE ?)")
        params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])
    if min_price is not None:
        clauses.append("p.avg_price >= ?")
        params.append(min_price)
    if max_price is not None:
        clauses.append("p.avg_price <= ?")
        params.append(max_price)
    if min_rating is not None:
        clauses.append("p.avg_rating >= ?")
        params.append(min_rating)

    where = " AND ".join(clauses)
    order_col = f"p.{SORTABLE.get(sort_by, 'avg_price')}"
    direction = "DESC" if descending else "ASC"

    total = scalar(f"SELECT count(*) FROM mart_product_performance p WHERE {where}", params)
    rows = query(
        f"""SELECT p.* EXCLUDE (product_name), p.product_name, s.segment_name
            FROM mart_product_performance p
            LEFT JOIN product_segment s USING (product_id)
            WHERE {where}
            ORDER BY {order_col} {direction}
            LIMIT ? OFFSET ?""",
        [*params, page_size, (page - 1) * page_size],
    )
    return rows, int(total or 0)


def get_product(product_id: int) -> dict | None:
    rows = query(
        """SELECT p.* EXCLUDE (product_name), p.product_name, s.segment_name
           FROM mart_product_performance p
           LEFT JOIN product_segment s USING (product_id)
           WHERE p.product_id = ?""",
        [product_id],
    )
    return rows[0] if rows else None


def price_history(product_id: int) -> list[dict]:
    return query(
        """SELECT dd.full_date AS observed_date, f.price, f.original_price,
                  f.discount_percentage, f.rating, f.sales_velocity
           FROM fact_price_observation f
           JOIN dim_date dd ON dd.date_sk = f.date_sk
           WHERE f.product_nk = ?
           ORDER BY dd.full_date""",
        [product_id],
    )


def forecast(product_id: int, target: str) -> list[dict]:
    return query(
        """SELECT forecast_date, yhat, yhat_lower, yhat_upper, model_run_id
           FROM ml_forecast WHERE product_id = ? AND target = ?
           ORDER BY forecast_date""",
        [product_id, target],
    )


def recommendations(product_id: int) -> list[dict]:
    return query(
        """SELECT r.recommended_product_id AS product_id, r.rank, r.similarity, r.reason,
                  p.product_name, p.category, p.brand, p.avg_price, p.avg_rating, p.image_url
           FROM ml_recommendation r
           JOIN mart_product_performance p ON p.product_id = r.recommended_product_id
           WHERE r.product_id = ? ORDER BY r.rank""",
        [product_id],
    )


def anomalies(limit: int) -> list[dict]:
    return query(
        """SELECT a.product_id, p.product_name, p.category, a.observed_date, a.price,
                  a.price_pct_change, a.robust_z, a.iforest_score, a.anomaly_type
           FROM ml_anomaly a
           JOIN mart_product_performance p USING (product_id)
           ORDER BY abs(a.robust_z) DESC LIMIT ?""",
        [limit],
    )


def top_deals(limit: int) -> list[dict]:
    return query("SELECT * FROM mart_trending_deals LIMIT ?", [limit])


def category_daily() -> list[dict]:
    return query("SELECT * FROM agg_category_daily ORDER BY category, full_date")


def facets() -> dict[str, list[str]]:
    return {
        "categories": [
            r["category"]
            for r in query("SELECT DISTINCT category FROM mart_product_performance ORDER BY 1")
        ],
        "brands": [
            r["brand"]
            for r in query(
                "SELECT DISTINCT brand FROM mart_product_performance "
                "WHERE brand IS NOT NULL ORDER BY 1"
            )
        ],
        "segments": [
            r["segment_name"]
            for r in query("SELECT DISTINCT segment_name FROM product_segment ORDER BY 1")
        ],
    }


def kpis() -> dict:
    row = query(
        """SELECT
             (SELECT count(*) FROM dim_product WHERE is_current)          AS products,
             (SELECT count(DISTINCT category) FROM mart_product_performance) AS categories,
             (SELECT count(DISTINCT brand) FROM mart_product_performance) AS brands,
             (SELECT count(*) FROM fact_price_observation)                AS warehouse_rows,
             (SELECT count(*) FROM mart_trending_deals)                   AS active_deals,
             (SELECT count(*) FROM ml_anomaly)                            AS anomalies,
             (SELECT round(avg(avg_price), 2) FROM mart_product_performance) AS avg_price,
             (SELECT round(avg(avg_discount), 2) FROM mart_product_performance) AS avg_discount"""
    )[0]
    dq = query("SELECT * FROM dq_report ORDER BY computed_at DESC LIMIT 1")
    row["quality"] = dq[0] if dq else None
    return row


def insights() -> list[dict]:
    """Rule-generated business insights over the last 7 vs prior 7 days."""
    return query(
        """WITH ranked AS (
             SELECT category, full_date, avg_price,
                    max(full_date) OVER (PARTITION BY category) AS latest
             FROM agg_category_daily
           ), windows AS (
             SELECT category,
                    avg(avg_price) FILTER (WHERE full_date >  latest - INTERVAL 7 DAY) AS recent,
                    avg(avg_price) FILTER (WHERE full_date <= latest - INTERVAL 7 DAY
                                             AND full_date > latest - INTERVAL 14 DAY) AS prior
             FROM ranked GROUP BY category
           )
           SELECT category,
                  round(100.0 * (recent - prior) / nullif(prior, 0), 1) AS pct_change_7d,
                  CASE WHEN recent > prior THEN 'up' ELSE 'down' END    AS direction
           FROM windows WHERE prior IS NOT NULL
           ORDER BY abs(recent - prior) / nullif(prior, 0) DESC"""
    )
