import { inventory, metrics, stockPools, yearLabel } from '../data'
import { count, money, pct } from '../format'
import type { ChartTheme } from '../theme'

/** Inventory health for each boutique in the selected year, as a table with inline meters. */
export function InventoryTable({ theme, selected }: { theme: ChartTheme; selected: string }) {
  const rows = stockPools
    .map((pool) => inventory.find((r) => r.fiscal_year === selected && r.stock_pool === pool))
    .filter((r) => r !== undefined)
  const maxAged = Math.max(0.2, ...inventory.map((r) => r.aged_inventory_share))

  return (
    <section className="card" aria-labelledby="inventory-title">
      <header className="card-header">
        <div>
          <h2 id="inventory-title">Inventory health, {yearLabel(selected)}</h2>
          <p className="card-subtitle">Stock at the end of the period, by the boutique it sits in.</p>
        </div>
      </header>
      <div className="table-scroll">
        <table className="data-table inventory-table">
          <thead>
            <tr>
              <th scope="col">Boutique</th>
              <th scope="col">{metrics.sell_through_rate.label}</th>
              <th scope="col">Units on hand</th>
              <th scope="col">Cost on hand</th>
              <th scope="col">Aged 90+ days</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.stock_pool}>
                <th scope="row">
                  <span
                    className="legend-swatch"
                    style={{ background: theme.series[stockPools.indexOf(r.stock_pool)] }}
                    aria-hidden="true"
                  />
                  {r.stock_pool}
                </th>
                <td>{pct(r.sell_through_rate)}</td>
                <td>{count(r.units_on_hand)}</td>
                <td>{money(r.inventory_cost_on_hand)}</td>
                <td>
                  <span className="meter-cell">
                    <span className="meter" aria-hidden="true">
                      <span className="meter-fill" style={{ width: `${(r.aged_inventory_share / maxAged) * 100}%` }} />
                    </span>
                    {pct(r.aged_inventory_share)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <footer className="card-footer">
        {metrics.sell_through_rate.label} · {metrics.units_on_hand.label} · {metrics.aged_inventory_share.label} · owned by{' '}
        {metrics.aged_inventory_share.owner}
      </footer>
    </section>
  )
}
