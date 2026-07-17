select
    product_id,
    recommended_product_id,
    rank,
    similarity,
    reason
from read_parquet('{{ var("lake_root") }}/gold/ml/recommendations.parquet')
