import { metrics, type MetricName } from '../data'
import type { Delta } from '../delta'

interface Props {
  metric: MetricName
  value: string
  delta?: Delta
  note?: string
  hero?: boolean
}

export function StatTile({ metric, value, delta, note, hero }: Props) {
  const def = metrics[metric]
  return (
    <div className={hero ? 'tile tile-hero' : 'tile'}>
      <div className="tile-label">
        {def.label}
        <span className="definition" tabIndex={0} aria-label={`Definition of ${def.label}`}>
          <span aria-hidden="true">i</span>
          <span className="definition-popover" role="tooltip">
            <strong>{def.label}</strong>
            {def.description}
            <span className="definition-meta">
              {def.certified ? 'Certified' : 'Not certified'}
              {def.owner ? ` · ${def.owner}` : ''}
            </span>
          </span>
        </span>
      </div>
      <div className="tile-value">{value}</div>
      {delta ? (
        <div className={`tile-delta ${delta.direction === 'flat' ? '' : delta.good ? 'good' : 'bad'}`}>
          <span aria-hidden="true">{delta.direction === 'up' ? '▲' : delta.direction === 'down' ? '▼' : '■'}</span>{' '}
          {delta.text} <span className="tile-versus">vs {delta.versus}</span>
        </div>
      ) : (
        note && <div className="tile-note">{note}</div>
      )}
    </div>
  )
}
