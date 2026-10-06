import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import RunList from './RunList.jsx'

export default function CommandCenter() {
  const [businesses, setBusinesses] = useState(null)
  const [team, setTeam] = useState([])
  const [runs, setRuns] = useState([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const fileInput = useRef(null)

  useEffect(() => {
    api.businesses().then(setBusinesses).catch((e) => setError(e.message))
    api.team().then(setTeam).catch(() => {})
    api.runs().then(setRuns).catch(() => {})
  }, [])

  async function create(e) {
    e.preventDefault()
    setError('')
    try {
      const biz = await api.createBusiness(name, description)
      window.location.hash = `#/business/${biz.id}`
    } catch (err) {
      setError(err.message)
    }
  }

  async function importProfile(e) {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    setError('')
    try {
      const profile = JSON.parse(await file.text())
      const biz = await api.importBusiness(profile)
      window.location.hash = `#/business/${biz.id}`
    } catch (err) {
      setError(err instanceof SyntaxError ? "That file isn't a valid profile (.json)." : err.message)
    }
  }

  const names = Object.fromEntries((businesses || []).map((b) => [b.id, b.name]))

  return (
    <div className="home">
      <section className="hero">
        <h1>Command center</h1>
        <p>
          Set up a business with its SOPs and knowledge, then send the team a goal. A strategist briefs it, research
          checks the market, seven specialists plan in parallel, a reviewer cross-checks, and you approve the result.
        </p>
      </section>

      {error && <p className="error">{error}</p>}

      <section>
        <div className="section-head">
          <h2>Businesses</h2>
          <button onClick={() => fileInput.current.click()}>Import profile</button>
          <input ref={fileInput} type="file" accept=".json,application/json" hidden onChange={importProfile} />
        </div>
        <div className="biz-grid">
          {businesses?.map((b) => (
            <a key={b.id} href={`#/business/${b.id}`} className="card biz">
              <strong>{b.name}</strong>
              <span className="muted clamp">{b.description || 'No description yet'}</span>
              <span className="muted small-text">
                {b.document_count} docs · {b.run_count} runs
              </span>
            </a>
          ))}
          <form onSubmit={create} className="card biz new-biz">
            <strong>New business</strong>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. LeafLoop" />
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What it does, who it serves, where"
            />
            <button className="primary" disabled={!name.trim()}>
              Create
            </button>
          </form>
        </div>
      </section>

      {team.length > 0 && (
        <section>
          <h2>The team</h2>
          <div className="team-grid">
            {team.map((m) => (
              <div key={m.key} className={`card small stage-${m.stage}`}>
                <strong>{m.title}</strong>
                <span className="muted">{m.focus}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {runs.length > 0 && (
        <section>
          <h2>Recent runs</h2>
          <RunList runs={runs} businessNames={names} />
        </section>
      )}
    </div>
  )
}
