export interface TooltipRow {
  color?: string
  label: string
  value: string
}

/** Tooltip body: values lead, series names follow, each keyed with a short line of its color. */
export function TooltipCard({ title, rows }: { title: string; rows: TooltipRow[] }) {
  return (
    <div className="tooltip">
      <div className="tooltip-title">{title}</div>
      {rows.map((r) => (
        <div className="tooltip-row" key={r.label}>
          {r.color && <span className="tooltip-key" style={{ background: r.color }} aria-hidden="true" />}
          <span className="tooltip-value">{r.value}</span>
          <span className="tooltip-label">{r.label}</span>
        </div>
      ))}
    </div>
  )
}
