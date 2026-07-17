select
    product_id, product_name, category, brand,
    segment_id, segment_name,
    avg_price, price_volatility, avg_discount, avg_rating, avg_velocity
from read_parquet('{{ var("lake_root") }}/gold/segments/product_segments.parquet')
