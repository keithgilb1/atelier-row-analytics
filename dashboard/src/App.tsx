import { useState } from 'react'
import { CategoryMixChart, CompGrowthChart, SalesTrendChart, SellThroughChart } from './components/Charts'
import { InventoryTable } from './components/InventoryTable'
import { MetricGlossary } from './components/MetricGlossary'
import { StatTile } from './components/StatTile'
import { makeDelta } from './delta'
import {
  currentFiscalYear,
  fiscalYearBounds,
  isPartialYear,
  lastSaleDate,
  priorYear,
  scorecard,
  selectableYears,
  yearLabel,
} from './data'
import { count, days, longDate, money, pct, signedPct } from './format'
import { useChartTheme } from './theme'

const REPO_URL = 'https://github.com/keithgilb1/atelier-row-analytics'

export default function App() {
  const [selected, setSelected] = useState(currentFiscalYear)
  const theme = useChartTheme()

  const row = scorecard.find((r) => r.fiscal_year === selected)!
  const prior = scorecard.find((r) => r.fiscal_year === priorYear(selected))
  const partial = isPartialYear(selected)
  const priorFull = prior && !isPartialYear(prior.fiscal_year)
  const versus = prior ? yearLabel(prior.fiscal_year) : ''
  const period = partial
    ? `${longDate(fiscalYearBounds(selected).start)} to ${longDate(lastSaleDate)}`
    : `${longDate(fiscalYearBounds(selected).start)} to ${longDate(fiscalYearBounds(selected).end)}`

  return (
    <div className="page">
      <header className="masthead">
        <div className="brand">
          <span className="wordmark">Atelier Row</span>
          <span className="brand-divider" aria-hidden="true" />
          <span className="brand-sub">Executive dashboard</span>
        </div>
        <p className="provenance">
          Data through {longDate(lastSaleDate)}.
          <div> </div>
          All data is read from the dbt semantic layer, which is only updated when generated.
          <div> </div>
          <a href={REPO_URL}>How it's built</a>
        </p>
      </header>

      <nav className="filters" aria-label="Fiscal year">
        <span className="filters-label">Fiscal year</span>
        <div className="segmented" role="radiogroup" aria-label="Fiscal year">
          {selectableYears.map((fy) => (
            <button
              key={fy}
              type="button"
              role="radio"
              aria-checked={fy === selected}
              className={fy === selected ? 'segment active' : 'segment'}
              onClick={() => setSelected(fy)}
            >
              {yearLabel(fy)}
            </button>
          ))}
        </div>
        <span className="filters-window">{period}</span>
      </nav>

      <main>
        <section className="kpis" aria-label={`Headline metrics, ${yearLabel(selected)}`}>
          <StatTile
            hero
            metric="comp_store_sales_growth"
            value={row.comp_store_sales_growth == null ? 'n/a' : signedPct(row.comp_store_sales_growth)}
            note={
              prior?.comp_store_sales_growth != null
                ? `${versus}: ${signedPct(prior.comp_store_sales_growth)}. Same days last year, boutiques only.`
                : 'Same days last year, boutiques only.'
            }
          />
          <div className="tile-grid">
            <StatTile
              metric="net_sales"
              value={money(row.net_sales)}
              delta={!partial && priorFull ? makeDelta(row.net_sales, prior.net_sales, versus, 'relative') : undefined}
              note={partial ? 'Year to date' : undefined}
            />
            <StatTile
              metric="units_sold"
              value={count(row.units_sold)}
              delta={!partial && priorFull ? makeDelta(row.units_sold, prior.units_sold, versus, 'relative') : undefined}
              note={partial ? 'Year to date' : undefined}
            />
            <StatTile
              metric="comp_sales_growth"
              value={row.comp_sales_growth == null ? 'n/a' : signedPct(row.comp_sales_growth)}
              note="All channels, including online"
            />
            <StatTile
              metric="gross_margin_pct"
              value={pct(row.gross_margin_pct)}
              delta={makeDelta(row.gross_margin_pct, prior?.gross_margin_pct, versus, 'points')}
            />
            <StatTile
              metric="average_selling_price"
              value={money(row.average_selling_price)}
              delta={makeDelta(row.average_selling_price, prior?.average_selling_price, versus, 'relative')}
            />
            <StatTile
              metric="average_days_to_sell"
              value={days(row.average_days_to_sell)}
              delta={makeDelta(row.average_days_to_sell, prior?.average_days_to_sell, versus, 'days', false)}
            />
          </div>
        </section>

        <div className="grid">
          <SalesTrendChart theme={theme} selected={selected} />
          <CompGrowthChart theme={theme} selected={selected} />
          <SellThroughChart theme={theme} selected={selected} />
          <InventoryTable theme={theme} selected={selected} />
          <CategoryMixChart theme={theme} selected={selected} />
        </div>

        <MetricGlossary />
      </main>

      <footer className="page-footer">
        Atelier Row is a fictional resale retailer. The data is synthetic, generated with a fixed seed, and rebuilt
        by <code>make all</code>. Built with React, Vite and Recharts on top of dbt, DuckDB and MetricFlow.{' '}
        <a href={REPO_URL}>Source on GitHub</a>
      </footer>
    </div>
  )
}
