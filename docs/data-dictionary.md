# Data Dictionary

## Lake

| Layer / dataset | Grain | Notes |
|---|---|---|
| `raw/{source}/dt=…` | as delivered | Immutable; manifest JSON alongside every landing |
| `raw/_rejected/…` | row | Quarantine; carries `_dq_reason` |
| `bronze/products` | product | Typed, deduped, Pandera-validated |
| `bronze/price_facts` | source fact | Contract-validated observations |
| `silver/products` | product | Conformed: derived category/subcategory, inferred brand, audience, parsed `color_options`, `source_*` lineage columns |
| `silver/price_observations/month=…` | product × day | `time_id` resolved to real dates; monthly Hive partitions |
| `gold/features/product_daily_features` | product × day | Lags (1, 7), rolling mean/std (7, 30), pct change, calendar features |
| `gold/aggregates/category_daily` | category × day | Market rollup |
| `gold/segments/product_segments` | product | K-Means segment (Value / Premium / Deal-Driven / Standard), price-ranked labels |
| `gold/ml/*` | see below | Batch model scores |
| `gold/quality/quality_report` | run | 5-dimension DQ score |

## Warehouse marts (dbt)

| Relation | Grain | Key columns |
|---|---|---|
| `dim_product` | product × version (SCD2) | `product_sk`, `valid_from/to`, `is_current`, `audience`, `color_options` |
| `dim_date` | day | `date_sk` (yyyymmdd), calendar attributes |
| `fact_price_observation` | product × day | FKs to both dims; incremental with 3-day late-arrival window |
| `agg_category_daily` | category × day | Pre-computed dashboard rollup |
| `mart_product_performance` | product (current) | Price stats, volatility, ratings — legacy view, matured |
| `mart_trending_deals` | product | Latest observation with discount ≥ 15% |
| `ml_forecast` | product × horizon day × target | `yhat`, 90% band, `model_run_id` |
| `ml_anomaly` | flagged observation | `robust_z`, `iforest_score`, `anomaly_type` |
| `ml_recommendation` | product × rank | similarity + human-readable reason |
| `product_segment` | product | Segment + behavioural profile |
| `dq_report` | run | Composite DQ published to the console |

## DQ score dimensions

completeness (0.25) · uniqueness (0.25) · validity (0.20) · consistency (0.15) · freshness (0.15, linear 30-day decay). SLO: composite ≥ 0.90, enforced by the `lake_medallion` DAG.
