-- One row per piece. A piece is unique, so the product dimension is at piece grain.
select
    inventory_id,
    brand,
    model_category,
    model,
    model_name,
    special_model_name,
    model_year,
    color,
    color_family,
    leather,
    leather_type,
    is_exotic,
    has_cites,
    hardware,
    sellier_retourne,
    is_verso,
    condition,
    is_box_fresh
from {{ ref('stg_product_detail') }}
