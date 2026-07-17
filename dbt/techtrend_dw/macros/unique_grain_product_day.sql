{% test unique_grain_product_day(model) %}
-- Fails if the declared grain (product x day) is violated upstream.
select product_id, observed_date, count(*) as n
from {{ model }}
group by 1, 2
having count(*) > 1
{% endtest %}
