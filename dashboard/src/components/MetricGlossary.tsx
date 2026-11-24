import { useState } from 'react'
import { metrics } from '../data'

/**
 * Every metric on the page with its governed definition, straight from the semantic manifest.
 * Collapsed by default so the definitions don't crowd the page; each tile's "i" still shows its own.
 */
export function MetricGlossary() {
  const [open, setOpen] = useState(false)
  const entries = Object.entries(metrics).sort(([, a], [, b]) => a.label.localeCompare(b.label))
  return (
    <section className="glossary" aria-labelledby="glossary-title">
      <header className="glossary-header">
        <div>
          <h2 id="glossary-title">Metric definitions</h2>
          <p className="card-subtitle">
            Each metric is defined once in the MetricFlow semantic layer. This page, the AI agent and the parity tests
            all read the same definitions.
          </p>
        </div>
        <button
          type="button"
          className="ghost-button"
          aria-expanded={open}
          aria-controls="glossary-list"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? 'Hide definitions' : `Show all ${entries.length} definitions`}
        </button>
      </header>
      <dl id="glossary-list" className="glossary-grid" hidden={!open}>
        {entries.map(([name, m]) => (
          <div key={name} className="glossary-item">
            <dt>
              {m.label}
              {m.certified && <span className="badge">Certified</span>}
            </dt>
            <dd>{m.description || 'No description.'}</dd>
            <dd className="glossary-meta">
              <code>{name}</code>
              {m.owner && <> · {m.owner}</>}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
