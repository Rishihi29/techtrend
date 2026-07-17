-- Current best deals: latest observation per product with a material
-- discount. Preserves the legacy v_trending_deals rule (>=15%).
with latest as (
    select f.*, row_number() over (partition by f.product_nk order by f.date_sk desc) as rn
    from {{ ref('fact_price_observation') }} f
)
select
    dp.product_nk        as product_id,
    dp.product_name,
    dp.category,
    dp.brand,
    dp.image_url,
    l.price              as current_price,
    l.original_price,
    l.discount_percentage,
    l.rating,
    dd.full_date         as observed_date
from latest l
join {{ ref('dim_product') }} dp on dp.product_sk = l.product_sk
join {{ ref('dim_date') }} dd on dd.date_sk = l.date_sk
where l.rn = 1 and l.discount_percentage >= 15.0
order by l.discount_percentage desc
