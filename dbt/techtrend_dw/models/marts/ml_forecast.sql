-- Batch model scores published by the ML scoring pipeline (gold layer).
select
    product_id,
    forecast_date,
    target,
    yhat,
    yhat_lower,
    yhat_upper,
    model_run_id
from read_parquet('{{ var("lake_root") }}/gold/ml/forecast_*.parquet')
