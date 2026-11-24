import { useId, useState, type ReactNode } from 'react'
import { metrics, type MetricName } from '../data'

export interface TableView {
  columns: string[]
  rows: (string | number)[][]
}

interface Props {
  title: string
  subtitle?: ReactNode
  metricNames: MetricName[]
  table: TableView
  legend?: ReactNode
  children: ReactNode
  className?: string
}

/** A card holding one chart, with a table view of the same rows and the governed definitions it uses. */
export function ChartCard({ title, subtitle, metricNames, table, legend, children, className }: Props) {
  const [showTable, setShowTable] = useState(false)
  const id = useId()
  const owners = [...new Set(metricNames.map((m) => metrics[m]?.owner).filter(Boolean))]

  return (
    <section className={`card ${className ?? ''}`} aria-labelledby={`${id}-title`}>
      <header className="card-header">
        <div>
          <h2 id={`${id}-title`}>{title}</h2>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
        <button
          type="button"
          className="ghost-button"
          aria-pressed={showTable}
          onClick={() => setShowTable((v) => !v)}
        >
          {showTable ? 'Show chart' : 'Show table'}
        </button>
      </header>

      {legend && !showTable && <div className="legend">{legend}</div>}

      {showTable ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {table.columns.map((c) => (
                  <th key={c} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="chart-body">{children}</div>
      )}

      <footer className="card-footer">
        {metricNames.map((m) => metrics[m]?.label).join(' · ')}
        {owners.length > 0 && <> · owned by {owners.join(' and ')}</>}
      </footer>
    </section>
  )
}

export function LegendItem({ color, label, shape = 'rect' }: { color: string; label: string; shape?: 'rect' | 'line' }) {
  return (
    <span className="legend-item">
      <span
        className={shape === 'line' ? 'legend-line' : 'legend-swatch'}
        style={{ background: color }}
        aria-hidden="true"
      />
      {label}
    </span>
  )
}
