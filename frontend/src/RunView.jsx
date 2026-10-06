import { useEffect, useState } from 'react'
import { api } from './api.js'
import Markdown from './Markdown.jsx'
import { BUSY, STATUS_LABELS, STEPS } from './status.js'

function Stepper({ status }) {
  const current = STEPS.findIndex((s) => s.statuses.includes(status))
  return (
    <ol className="stepper">
      {STEPS.map((step, i) => {
        const state = status === 'done' || i < current ? 'done' : i === current ? 'active' : ''
        return (
          <li key={step.label} className={state}>
            <span className="dot">{state === 'done' ? '✓' : i + 1}</span>
            {step.label}
          </li>
        )
      })}
    </ol>
  )
}

function Section({ title, subtitle, text, writing }) {
  return (
    <article className={`card section ${writing ? 'writing' : ''}`}>
      <header>
        <strong>{title}</strong>
        {subtitle && <span className="muted">{subtitle}</span>}
        {writing && <span className="pill live">writing…</span>}
      </header>
      {text ? <Markdown text={text} /> : <p className="muted">{writing ? 'Thinking…' : 'Waiting for the brief'}</p>}
    </article>
  )
}

function ApprovalPanel({ run, team }) {
  const [feedback, setFeedback] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const hasFeedback = Object.values(feedback).some((v) => v.trim())

  async function act(fn) {
    setBusy(true)
    setError('')
    try {
      await fn()
      setFeedback({})
    } catch (err) {
      setError(err.message)
    }
    setBusy(false)
  }

  return (
    <section className="card approval">
      <h2>Your call</h2>
      <p className="muted">
        Read the reviewer's notes above. Approve to get the final plan, or tell specific specialists what to change.
      </p>
      <div className="feedback-grid">
        {team.map((m) => (
          <label key={m.key}>
            {m.title}
            <textarea
              rows={2}
              value={feedback[m.key] || ''}
              onChange={(e) => setFeedback({ ...feedback, [m.key]: e.target.value })}
              placeholder="Leave blank if it's fine"
            />
          </label>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button disabled={busy || !hasFeedback} onClick={() => act(() => api.revise(run.id, feedback))}>
          Send back for changes
        </button>
        <button className="primary" disabled={busy || hasFeedback} onClick={() => act(() => api.approve(run.id))}>
          Approve & write final plan
        </button>
      </div>
    </section>
  )
}

function downloadMarkdown(run) {
  const blob = new Blob([run.sections.final], { type: 'text/markdown' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${(run.company || 'launch-plan').toLowerCase().replace(/\W+/g, '-')}.md`
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function RunView({ runId }) {
  const [run, setRun] = useState(null)
  const [writing, setWriting] = useState(new Set())
  const [team, setTeam] = useState([])
  const [lost, setLost] = useState(false)

  useEffect(() => {
    api.team().then(setTeam).catch(() => {})
  }, [])

  useEffect(() => {
    const source = api.events(runId)
    const setSection = (section, fn) =>
      setRun((r) => r && { ...r, sections: { ...r.sections, [section]: fn(r.sections[section] || '') } })
    const markWriting = (section, on) =>
      setWriting((w) => {
        const next = new Set(w)
        on ? next.add(section) : next.delete(section)
        return next
      })

    source.onopen = () => setLost(false)
    source.onerror = () => setLost(true)
    source.onmessage = (e) => {
      const ev = JSON.parse(e.data)
      if (ev.type === 'snapshot') setRun(ev.run)
      else if (ev.type === 'status') setRun((r) => r && { ...r, status: ev.status })
      else if (ev.type === 'section_start') {
        setSection(ev.section, () => '')
        markWriting(ev.section, true)
      } else if (ev.type === 'delta') setSection(ev.section, (t) => t + ev.text)
      else if (ev.type === 'section_done') {
        setSection(ev.section, () => ev.text)
        markWriting(ev.section, false)
      }
    }
    return () => source.close()
  }, [runId])

  if (!run) return <p className="muted center">{lost ? "Couldn't load this run." : 'Loading…'}</p>

  const s = run.sections
  const busy = BUSY.has(run.status)

  return (
    <div className="run">
      <div className="run-head">
        <div>
          <h1>{run.company || 'Untitled venture'}</h1>
          <p className="muted idea">{run.idea}</p>
        </div>
        <span className={`pill ${run.status === 'failed' ? 'bad' : busy ? 'live' : 'ok'}`}>
          {STATUS_LABELS[run.status] || run.status}
        </span>
      </div>
      <Stepper status={run.status} />
      {lost && busy && <p className="error">Lost connection to the backend, retrying…</p>}
      {run.status === 'failed' && <p className="error">Something went wrong: {run.error}</p>}

      {s.final !== undefined && (
        <section className="card final">
          <header>
            <h2>Launch plan</h2>
            {run.status === 'done' && <button onClick={() => downloadMarkdown(run)}>Download .md</button>}
          </header>
          <Markdown text={s.final} />
        </section>
      )}

      <Section title="Strategy brief" subtitle="Lead Strategist" text={s.brief} writing={writing.has('brief')} />

      <div className="specialists">
        {team.map((m) => (
          <Section key={m.key} title={m.title} subtitle={m.focus} text={s[m.key]} writing={writing.has(m.key)} />
        ))}
      </div>

      {s.review !== undefined && (
        <Section title="Review" subtitle="Cross-checks the team's work" text={s.review} writing={writing.has('review')} />
      )}

      {run.status === 'awaiting_approval' && <ApprovalPanel run={run} team={team} />}
    </div>
  )
}
