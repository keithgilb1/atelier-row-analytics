-- Flags sales priced far from comparable pieces, using a robust z-score (median and MAD) within
-- peer groups of the same model, leather and condition. Median-based statistics are used so a
-- few extreme prices cannot hide themselves by inflating the mean and standard deviation.
-- Reviewed weekly by the pricing team. A warn-level test reports new flags without failing the build.
with priced as (
    select
        s.sale_id,
        s.sale_date,
        s.location_id,
        p.model_name,
        p.leather,
        p.condition,
        s.net_sales_amount::double as price,
        (s.gross_margin_amount / nullif(s.net_sales_amount, 0))::double as margin_pct
    from {{ ref('fct_sales') }} as s
    inner join {{ ref('dim_product') }} as p using (inventory_id)
),

peer_median as (
    select model_name, leather, condition, median(price) as median_price, count(*) as peer_count
    from priced
    group by all
),

peer_mad as (
    select pr.model_name, pr.leather, pr.condition, median(abs(pr.price - pm.median_price)) as mad_price
    from priced as pr
    inner join peer_median as pm using (model_name, leather, condition)
    group by all
)

select
    pr.*,
    pm.median_price,
    pm.peer_count,
    md.mad_price,
    -- 1.4826 scales MAD to be comparable with a standard deviation for normal data.
    -- The spread is floored at 2% of the peer median so tightly priced groups don't flag rounding noise.
    (pr.price - pm.median_price) / greatest(1.4826 * md.mad_price, 0.02 * pm.median_price) as robust_z,
    abs((pr.price - pm.median_price) / greatest(1.4826 * md.mad_price, 0.02 * pm.median_price)) > 3.5
        or pr.margin_pct not between 0.30 and 0.45 as is_flagged
from priced as pr
inner join peer_median as pm using (model_name, leather, condition)
inner join peer_mad as md using (model_name, leather, condition)
where pm.peer_count >= 10
