select
    product_id,
    observed_date,
    price,
    price_pct_change,
    robust_z,
    iforest_score,
    anomaly_type,
    model_run_id
from read_parquet('{{ var("lake_root") }}/gold/ml/anomalies.parquet')
