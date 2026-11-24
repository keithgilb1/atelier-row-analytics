# Atelier Row: a synthetic luxury-handbag resale warehouse

Atelier Row is a fictional resale boutique for high-end handbags. It has stores in New York City (Fifth Avenue), Los Angeles (Rodeo Drive, Beverly Hills) and Miami (Design District), plus an online channel, Online (HQ), which ships from New York stock. The generator simulates daily buy-ins, a four-stage authentication pipeline, stock on hand and sales, then writes the warehouse as CSVs and a DuckDB file. It works the same way as the Quillstack generator in [keithgilb1/quillstack](https://github.com/keithgilb1/quillstack).

## Quick start

```bash
cd generator
pip install numpy pandas duckdb
python atelier_row_generator.py                 # seed 42 -> ./atelier_row_data
python atelier_row_generator.py --seed 7 --out run_seed7
python atelier_row_generator.py --no-duckdb     # CSVs only
```

The same `--seed` always gives the same data. The script runs its own checks (keys, nulls, margin, snapshot consistency) and prints a summary.

## What is in the output

| Table | Rows (seed 42) | Grain | Key |
|---|---:|---|---|
| `calendar` | 4,383 | day, 2016 to 2027 | `calendar_date` |
| `locations` | 4 | location | `location_id` |
| `customers` | 5,907 | customer (buyers and sellers) | `customer_id` |
| `purchasing` | 23,909 | buy-in (one per piece) | `purchase_id` |
| `product_detail` | 23,909 | piece | `inventory_id` |
| `sales` | 23,366 | sale (sold pieces only) | `sale_id` |
| `inventory` | 893,212 | piece on hand, per day | `snapshot_date` + `inventory_id` |

## Data model

```
calendar (date)

locations ──< purchasing >── customers ──< sales >── locations
               │ 1:1                          │
               ▼                              │
           product_detail ── inventory ───────┘
           (inventory_id)    (daily snapshot,
                              sale_id set on the sale day)
```

Relationships:

- `purchasing.customer_id` is the seller (customer buy-in). `sales.customer_id` is the buyer. The same customer can do both.
- `purchasing.inventory_id` and `product_detail.inventory_id` are 1:1 with each other. `purchase_id` maps 1:1 to `inventory_id` by number (`PUR-000123` is `INV-000123`).
- `inventory.purchase_id` links each daily row back to the buy-in. `inventory.sale_id` is filled only on the day the piece sells.
- `sales.inventory_id` links each sale to its piece.

## Field notes

- **calendar**: fiscal year runs July to June and is named by the year it ends (FY2026 = Jul 2025 to Jun 2026). `fiscal_quarter` is Q1 (Jul to Sep) through Q4 (Apr to Jun). `fiscal_month_number` 1 = July.
- **locations**: `close_date` is null for every location, as specified. Online (HQ) shares the New York address.
- **customers**: `birthday_ddmm` is text in DD/MM format (no year). `customer_phone` is E.164 (for example `+447...`). US and Canadian numbers use the reserved 555 range. All addresses and names are fictional.
- **purchasing**: `purchase_price` = 60% of market value (-40%). `stage` is the stage as of 2026-11-21: Contract Completed, Authentication, Customer Paid, or Available to Stock. The pipeline is 3 to 8 days from contract to stock.
- **sales**: `sales_price` is the market value less a negotiated discount on about 35% of pieces (0.5% to 4%). Median realised margin is 40.0%. `payment_type` is Credit Card (about 80%) or Wire Transfer, with wires more common above $100k and for international buyers. `delivery_type` is None, Local Delivery (same metro as the store) or Shipping Delivery (all online orders).
- **product_detail**: `brand` is written as "Hermes". `special_model_name` and `notes` are blank except for the three manual special-edition records defined in `MANUAL_SPECIALS` in the script. `has_cites` is Y or N for exotic leather and N/A for standard. `sellier_retourne` is S, R or O (O for non-Birkin and non-Kelly models).
- **inventory**: a row for each piece on hand each day, from the day it reaches the floor through its sale day. `sale_id` is null except on the sale day. Null `sale_id` on unsold pieces is expected. The snapshot covers 2021-06-01 to 2026-11-21.

## Pricing rules

| Category | Model / leather | Market value (approx.) |
|---|---|---|
| Birkin, standard | 25 / 30 / 35 / 40 / 40 HAC | $28k / $21k / $18.5k / $16.5k / $15.2k, range $15k to $40k |
| Birkin 25 Sellier | discontinued, rare | $33k to $40k (top of the range) |
| Kelly, standard | Mini (highest demand) / 25 / 28 / 32 / Pochette / Danse | $33k / $24k / $20.5k / $18k / $16k / $15.5k, range $15k to $40k |
| Birkin and Kelly, exotic (15% of pieces) | Ostrich (cheapest), Lizard, Alligator, Crocodile (top) | $70k to $95k / $95k to $130k / $125k to $160k / $145k to $175k |
| Constance | Micro / Mini / 24 / Elan / To Go | $11k to $19k |
| Picotin | 18 / 22 / 26 / 33 | $2k to $6k |
| Evelyne | TPM / PM / GM / TGM | $1.8k to $6k |
| Garden Party | 30 / 36 / 49 / Voyage | $1.3k to $6.5k |
| Her Bag | 19 / 31 / 39 / 50 | $2k to $6k |

Modifiers applied on top: color tier (basic colors cheapest, rare colors up to 12% higher), leather (Togo and Epsom base, Box about 4% higher, Swift about 3% lower), condition (New 1.00, Full Set 0.98, Excellent Pre Loved 0.92, Pre Loved 0.85), Verso (+8%), Permabrass hardware (-6%) and vintage model years (-8%). Vintage pieces are never priced above current-year pieces.

Condition mix: New 40%, Full Set 35%, Excellent Pre Loved 15%, Pre Loved 10%. Box-fresh (New plus Full Set) is about 75% of sales.

## Assumptions to review

These are my choices where the spec was open or inconsistent. They are all set in the script, so you can change them and regenerate.

1. **Window.** Sales run 2021-06-01 to 2026-11-21, about 5.5 years. FY2021 and FY2027 are partial years. Opening stock was bought in the 60 days before 2021-06-01, so the purchasing table starts in April 2021.
2. **Volume.** Each store averages about 22 sales a week, slightly above the 20 you specified, because demand grows 4% a year and has seasonality. Online is 12 a week (not specified).
3. **Kelly 25.** It appears twice in the spec. I treated it as one model.
4. **Spelling.** "Aligator" is treated as Alligator. "Evelyn" is treated as Evelyne, as in the model list.
5. **Other model.** Priced $2k to $6k because the spec gave no range.
6. **Birkin 40 HAC.** Lowest of the Birkin sizes, as specified.
7. **Stock target.** Buy-ins adjust to hold about six weeks of demand on hand per location. Stock is not allowed to grow without limit.
8. **Online fulfilment.** Online sales come from New York stock. The inventory row keeps the New York location.
9. **Customers.** One pool of about 5,900 customers buys and sells. About 5,500 of them buy. Buyers are weighted so that a few are frequent, and about 84% of buyers buy more than once.
10. **Manual specials.** The three demo special-edition records in `MANUAL_SPECIALS` are fictional. Replace or extend them with real records as needed.

## Changing the model

- Prices and mix: `MODELS`, `EXOTIC`, `LEATHER_MULT`, `COLOR_TIER_MULT`, `CONDITION_MULT` near the top of the script.
- Volume and seasonality: `LOCATIONS` (`weekly_sales`), `SEASON`, `WEEKDAY`, `GROWTH`.
- Pipeline and stock: `TARGET_WEEKS_ON_HAND`, and the pipeline draws in `add_item`.
- Dates: `DATA_START`, `DATA_END`.
