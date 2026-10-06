import { useEffect, useState } from 'react'
import { api } from './api.js'
import { STATUS_LABELS } from './status.js'

export default function NewRun() {
  const [idea, setIdea] = useState('')
  const [company, setCompany] = useState('')
  const [team, setTeam] = useState([])
  const [runs, setRuns] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.team().then(setTeam).catch(() => {})
    api.runs().then(setRuns).catch(() => {})
  }, [])

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const run = await api.createRun(idea, company)
      window.location.hash = `#/run/${run.id}`
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="home">
      <section className="hero">
        <h1>Turn an idea into a launch plan</h1>
        <p>
          Describe your business idea. A strategist writes the brief, five specialists work on it in parallel, a
          reviewer checks their work against each other, and you approve before the final plan is written.
        </p>
        <form onSubmit={submit} className="card form">
          <label>
            Company or working name <span className="muted">(optional)</span>
            <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e.g. LeafLoop" />
          </label>
          <label>
            Your idea
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              rows={6}
              placeholder="e.g. A subscription that delivers and maintains live plants for small offices in Bangalore. Customers pay monthly; we swap plants every quarter."
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="primary" disabled={busy || idea.trim().length < 10}>
            {busy ? 'Starting…' : 'Assemble the team →'}
          </button>
        </form>
      </section>

      {team.length > 0 && (
        <section>
          <h2>The team</h2>
          <div className="team-grid">
            {team.map((m) => (
              <div key={m.key} className="card small">
                <strong>{m.title}</strong>
                <span className="muted">{m.focus}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {runs.length > 0 && (
        <section>
          <h2>Past runs</h2>
          <ul className="run-list">
            {runs.map((r) => (
              <li key={r.id}>
                <a href={`#/run/${r.id}`}>
                  <strong>{r.company || r.idea.slice(0, 60)}</strong>
                  <span className="muted">{new Date(r.created_at).toLocaleString()}</span>
                  <span className="pill">{STATUS_LABELS[r.status] || r.status}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
