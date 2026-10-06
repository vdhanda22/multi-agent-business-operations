import { STATUS_LABELS } from './status.js'

export default function RunList({ runs, businessNames = {} }) {
  return (
    <ul className="run-list">
      {runs.map((r) => (
        <li key={r.id}>
          <a href={`#/run/${r.id}`}>
            <span className="run-title">
              <strong>{businessNames[r.business_id] || r.company}</strong>
              <span className="muted">{r.idea.length > 90 ? `${r.idea.slice(0, 90)}…` : r.idea}</span>
            </span>
            <span className="muted small-text">{new Date(r.created_at).toLocaleString()}</span>
            <span className="pill">{STATUS_LABELS[r.status] || r.status}</span>
          </a>
        </li>
      ))}
    </ul>
  )
}
