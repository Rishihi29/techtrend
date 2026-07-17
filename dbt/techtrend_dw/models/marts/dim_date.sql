-- Conformed date dimension spanning observed history plus forecast horizon.
with bounds as (
    select
        min(observed_date)                       as start_date,
        max(observed_date) + interval 60 day     as end_date
    from {{ ref('stg_price_observations') }}
),
spine as (
    select unnest(generate_series(start_date, end_date, interval 1 day))::date as full_date
    from bounds
)
select
    cast(strftime(full_date, '%Y%m%d') as integer) as date_sk,
    full_date,
    extract(year from full_date)                   as year,
    extract(quarter from full_date)                as quarter,
    extract(month from full_date)                  as month,
    strftime(full_date, '%B')                      as month_name,
    cast(strftime(full_date, '%W') as integer)     as week_of_year,
    extract(isodow from full_date)                 as day_of_week,
    strftime(full_date, '%A')                      as day_name,
    extract(isodow from full_date) >= 6            as is_weekend
from spine
