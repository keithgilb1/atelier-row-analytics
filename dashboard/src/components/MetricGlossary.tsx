import { metrics } from '../data'

/** Every metric on the page with its governed definition, straight from the semantic manifest. */
export function MetricGlossary() {
  const entries = Object.entries(metrics).sort(([, a], [, b]) => a.label.localeCompare(b.label))
  return (
    <section className="glossary" aria-labelledby="glossary-title">
      <h2 id="glossary-title">Metric definitions</h2>
      <p className="card-subtitle">
        Each metric is defined once in the MetricFlow semantic layer. This page, the AI agent and the parity tests
        all read the same definitions.
      </p>
      <dl className="glossary-grid">
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
