-- Staging: silver price observations (grain: product x observed day).
select
    product_id,
    observed_date,
    price,
    original_price,
    discount_percentage,
    availability,
    stock_level,
    rating,
    review_count,
    sales_velocity,
    is_trending
from read_parquet('{{ var("lake_root") }}/silver/price_observations/month=*/*.parquet')
