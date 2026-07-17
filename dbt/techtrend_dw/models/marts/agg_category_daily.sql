-- Category-level daily market aggregate (pre-computed for dashboards).
select
    dp.category,
    dd.full_date,
    count(distinct f.product_nk)      as products_observed,
    avg(f.price)                      as avg_price,
    min(f.price)                      as min_price,
    max(f.price)                      as max_price,
    avg(f.discount_percentage)        as avg_discount,
    sum(f.sales_velocity)             as total_sales_velocity
from {{ ref('fact_price_observation') }} f
join {{ ref('dim_product') }} dp on dp.product_sk = f.product_sk
join {{ ref('dim_date') }} dd on dd.date_sk = f.date_sk
group by 1, 2
