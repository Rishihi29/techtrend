-- Staging: 1:1 with the silver products entity. Renaming and typing only.
select
    product_id,
    product_name,
    category,
    subcategory,
    brand,
    audience,
    color_options,
    base_price,
    base_rating,
    image_url
from read_parquet('{{ var("lake_root") }}/silver/products/products.parquet')
