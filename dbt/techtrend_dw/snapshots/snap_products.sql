{% snapshot snap_products %}
{#- SCD Type 2 over product attributes. Snapshots capture the *source*
    (silver products), so the snapshot DAG-node has no model dependencies
    and validity ranges accrue on every change dbt observes. -#}
{{
    config(
        target_schema='snapshots',
        unique_key='product_id',
        strategy='check',
        check_cols=['product_name', 'category', 'subcategory', 'brand', 'image_url'],
    )
}}
select
    product_id, product_name, category, subcategory, brand, audience, color_options,
    base_price, base_rating, image_url
from read_parquet('{{ var("lake_root") }}/silver/products/products.parquet')
{% endsnapshot %}
