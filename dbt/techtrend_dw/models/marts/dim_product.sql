-- SCD2 product dimension materialised from the dbt snapshot.
-- The *initial* row per product is backdated to the epoch: historical facts
-- predate the first snapshot run and must still resolve a dimension row
-- (standard SCD2 initial-load treatment).
with versions as (
    select *,
        row_number() over (partition by product_id order by dbt_valid_from) as version_n
    from {{ ref('snap_products') }}
)
select
    md5(cast(product_id as varchar) || '|' || cast(dbt_valid_from as varchar)) as product_sk,
    product_id                                     as product_nk,
    product_name,
    category,
    subcategory,
    brand,
    audience,
    color_options,
    base_price,
    base_rating,
    image_url,
    case when version_n = 1 then timestamp '1900-01-01'
         else dbt_valid_from end                   as valid_from,
    coalesce(dbt_valid_to, timestamp '9999-12-31') as valid_to,
    dbt_valid_to is null                           as is_current
from versions
