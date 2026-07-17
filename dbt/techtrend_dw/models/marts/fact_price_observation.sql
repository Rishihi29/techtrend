-- Grain: one row per product per observed day. Incremental delete+insert
-- keyed on the date, so daily reruns are idempotent. Facts join to the
-- SCD2 dimension row valid at observation time.
{{
    config(
        materialized='incremental',
        incremental_strategy='delete+insert',
        unique_key='date_sk',
    )
}}
select
    dp.product_sk,
    o.product_id                                        as product_nk,
    cast(strftime(o.observed_date, '%Y%m%d') as integer) as date_sk,
    o.price,
    o.original_price,
    o.discount_percentage,
    o.availability,
    o.stock_level,
    o.rating,
    o.review_count,
    o.sales_velocity,
    o.is_trending
from {{ ref('stg_price_observations') }} o
join {{ ref('dim_product') }} dp
  on dp.product_nk = o.product_id
 and o.observed_date >= cast(dp.valid_from as date)
 and o.observed_date <  cast(dp.valid_to   as date)
{% if is_incremental() %}
where cast(strftime(o.observed_date, '%Y%m%d') as integer) >
      coalesce((select max(date_sk) - 3 from {{ this }}), 0)  -- 3-day late-arrival window
{% endif %}
