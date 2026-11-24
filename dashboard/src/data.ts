// Typed access to the bundled semantic-layer export.
//
// src/data/atelier.json is written by `make dashboard-data`, which reads the governed MetricFlow
// saved queries. The dashboard only selects and formats these rows. It never recomputes a metric,
// so every number here matches the agent and the parity tests.
import raw from './data/atelier.json'

export type MetricName =
  | 'net_sales'
  | 'units_sold'
  | 'gross_margin_pct'
  | 'average_selling_price'
  | 'average_days_to_sell'
  | 'comp_store_sales_growth'
  | 'comp_sales_growth'
  | 'sell_through_rate'
  | 'units_on_hand'
  | 'inventory_cost_on_hand'
  | 'aged_inventory_share'

export interface MetricDefinition {
  label: string
  description: string
  owner: string | null
  certified: boolean
}

export interface ScorecardRow {
  fiscal_year: string
  net_sales: number
  units_sold: number
  gross_margin_pct: number
  average_selling_price: number
  average_days_to_sell: number
  comp_store_sales_growth: number | null
  comp_sales_growth: number | null
}

export interface InventoryRow {
  fiscal_year: string
  stock_pool: string
  sell_through_rate: number
  units_on_hand: number
  inventory_cost_on_hand: number
  aged_inventory_share: number
}

export interface SalesTrendRow {
  month: string
  channel: string
  net_sales: number
  units_sold: number
  gross_margin_pct: number
}

export interface CategoryRow {
  fiscal_year: string
  model_category: string
  net_sales: number
  units_sold: number
  gross_margin_pct: number
  average_days_to_sell: number
}

interface Export {
  source: string
  data_window: { first_sale_date: string; last_sale_date: string }
  metrics: Record<MetricName, MetricDefinition>
  executive_scorecard: ScorecardRow[]
  inventory_health: InventoryRow[]
  sales_trend: SalesTrendRow[]
  category_mix: CategoryRow[]
}

export const data = raw as unknown as Export

export const metrics = data.metrics
export const scorecard = data.executive_scorecard
export const inventory = data.inventory_health
export const salesTrend = data.sales_trend
export const categoryMix = data.category_mix

// Fiscal years run July to June and are named by the year they end (FY2027 = Jul 2026 to Jun 2027).
export function fiscalYearOf(isoDate: string): string {
  const [year, month] = isoDate.split('-').map(Number)
  return `FY${month >= 7 ? year + 1 : year}`
}

export function fiscalYearBounds(fy: string): { start: string; end: string } {
  const endYear = Number(fy.slice(2))
  return { start: `${endYear - 1}-07-01`, end: `${endYear}-06-30` }
}

const firstFy = fiscalYearOf(data.data_window.first_sale_date)
const lastFy = fiscalYearOf(data.data_window.last_sale_date)

/** A fiscal year the data only partly covers: the first (history starts mid-year) and the current one. */
export function isPartialYear(fy: string): boolean {
  const { start, end } = fiscalYearBounds(fy)
  return (
    (fy === firstFy && data.data_window.first_sale_date > start) ||
    (fy === lastFy && data.data_window.last_sale_date < end)
  )
}

export const currentFiscalYear = lastFy
export const lastSaleDate = data.data_window.last_sale_date

/** Years offered in the picker: every full year plus the current year to date. */
export const selectableYears = scorecard
  .map((r) => r.fiscal_year)
  .filter((fy) => !isPartialYear(fy) || fy === currentFiscalYear)

export function yearLabel(fy: string): string {
  return fy === currentFiscalYear && isPartialYear(fy) ? `${fy} YTD` : fy
}

export function priorYear(fy: string): string {
  return `FY${Number(fy.slice(2)) - 1}`
}

// Stock pools in a fixed order so each one keeps its color everywhere.
export const stockPools = [...new Set(inventory.map((r) => r.stock_pool))].sort()
export const channels = ['Store', 'Online'] as const
