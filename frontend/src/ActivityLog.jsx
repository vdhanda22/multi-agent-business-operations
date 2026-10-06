const fmtTime = (ts) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const fmtNum = (n) => (n || 0).toLocaleString()
const fmtSecs = (ms) => `${(ms / 1000).toFixed(1)}s`

function totals(entries) {
  const t = { input: 0, output: 0, cacheRead: 0, searches: 0, cost: 0, costKnown: true, calls: 0 }
  for (const e of entries) {
    const m = e.metrics
    if (e.kind !== 'finished' || !m) continue
    t.calls += 1
    t.input += (m.input_tokens || 0) + (m.cache_read_tokens || 0) + (m.cache_write_tokens || 0)
    t.output += m.output_tokens || 0
    t.cacheRead += m.cache_read_tokens || 0
    t.searches += m.web_searches || 0
    if (m.cost_usd == null) t.costKnown = false
    else t.cost += m.cost_usd
  }
  return t
}

export default function ActivityLog({ entries }) {
  const t = totals(entries)
  const cachePct = t.input ? Math.round((t.cacheRead / t.input) * 100) : 0

  return (
    <div className="activity">
      <div className="stats">
        <div className="card stat">
          <span className="muted">Agent calls</span>
          <strong>{t.calls}</strong>
        </div>
        <div className="card stat">
          <span className="muted">Input tokens</span>
          <strong>{fmtNum(t.input)}</strong>
          <span className="muted small-text">{cachePct}% from cache</span>
        </div>
        <div className="card stat">
          <span className="muted">Output tokens</span>
          <strong>{fmtNum(t.output)}</strong>
        </div>
        <div className="card stat">
          <span className="muted">Web searches</span>
          <strong>{t.searches}</strong>
        </div>
        <div className="card stat">
          <span className="muted">Est. cost</span>
          <strong>{t.costKnown ? `$${t.cost.toFixed(3)}` : '—'}</strong>
        </div>
      </div>

      <div className="card">
        <table className="log">
          <thead>
            <tr>
              <th>Time</th>
              <th>Agent</th>
              <th>Event</th>
              <th>Detail</th>
              <th className="num">Took</th>
              <th className="num">Tokens in / out</th>
              <th className="num">Cost</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => {
              const m = e.metrics || {}
              return (
                <tr key={e.id} className={`kind-${e.kind}`}>
                  <td className="muted">{fmtTime(e.ts)}</td>
                  <td>{e.agent}</td>
                  <td>
                    <span className={`tag ${e.kind}`}>{e.kind}</span>
                  </td>
                  <td className="detail">{e.detail}</td>
                  <td className="num">{m.duration_ms != null ? fmtSecs(m.duration_ms) : ''}</td>
                  <td className="num">
                    {m.output_tokens != null
                      ? `${fmtNum((m.input_tokens || 0) + (m.cache_read_tokens || 0) + (m.cache_write_tokens || 0))} / ${fmtNum(m.output_tokens)}`
                      : ''}
                  </td>
                  <td className="num">{m.cost_usd != null ? `$${m.cost_usd.toFixed(4)}` : ''}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {entries.length === 0 && <p className="muted">Nothing logged yet.</p>}
      </div>
    </div>
  )
}
