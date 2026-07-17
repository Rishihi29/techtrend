-- Product performance rollup. Preserves the business logic of the legacy
-- v_product_performance MySQL view, now tested and lineage-tracked.
select
    dp.product_nk                    as product_id,
    dp.product_name,
    dp.category,
    dp.subcategory,
    dp.brand,
    dp.audience,
    dp.image_url,
    dp.base_rating,
    avg(f.price)                     as avg_price,
    min(f.price)                     as min_price,
    max(f.price)                     as max_price,
    avg(f.rating)                    as avg_rating,
    max(f.review_count)              as total_reviews,
    avg(f.discount_percentage)       as avg_discount,
    stddev_samp(f.price) / nullif(avg(f.price), 0) as price_volatility,
    count(*)                         as data_points,
    avg(f.sales_velocity)            as avg_sales_velocity
from {{ ref('fact_price_observation') }} f
join {{ ref('dim_product') }} dp
  on dp.product_sk = f.product_sk and dp.is_current
group by 1, 2, 3, 4, 5, 6, 7, 8
