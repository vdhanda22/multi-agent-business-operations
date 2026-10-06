import { useEffect, useState } from 'react'
import { api } from './api.js'
import Markdown from './Markdown.jsx'
import RunList from './RunList.jsx'

function saveFile(name, text, type) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([text], { type }))
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}

function Profile({ biz, onSaved }) {
  const [name, setName] = useState(biz.name)
  const [description, setDescription] = useState(biz.description)
  const dirty = name !== biz.name || description !== biz.description

  async function save() {
    await api.updateBusiness(biz.id, name, description)
    onSaved()
  }

  return (
    <div className="card form">
      <label>
        Name
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Description <span className="muted">(every agent sees this)</span>
        <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <button disabled={!dirty || !name.trim()} onClick={save}>
        Save profile
      </button>
    </div>
  )
}

function Library({ biz, onChanged }) {
  const [kind, setKind] = useState('sop')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')

  async function loadFile(e) {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    setContent(await file.text())
    if (!title) setTitle(file.name.replace(/\.(md|txt|markdown)$/i, ''))
  }

  async function add(e) {
    e.preventDefault()
    setError('')
    try {
      await api.addDocument(biz.id, { kind, title, content })
      setTitle('')
      setContent('')
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(doc) {
    if (!confirm(`Delete "${doc.title}"?`)) return
    await api.deleteDocument(doc.id)
    if (open?.id === doc.id) setOpen(null)
    onChanged()
  }

  async function view(doc) {
    setOpen(open?.id === doc.id ? null : await api.document(doc.id))
  }

  const pct = Math.min(100, Math.round((biz.library_chars / biz.library_limit) * 100))

  return (
    <div className="library">
      <div className="card">
        <div className="section-head">
          <strong>Documents</strong>
          <span className="muted small-text">
            {biz.library_chars.toLocaleString()} / {biz.library_limit.toLocaleString()} characters
          </span>
        </div>
        <div className="meter">
          <span style={{ width: `${pct}%` }} />
        </div>
        {biz.documents.length === 0 && (
          <p className="muted">
            No documents yet. Add SOPs (how you do things) and knowledge (facts about your business) and every agent will
            follow them.
          </p>
        )}
        <ul className="doc-list">
          {biz.documents.map((d) => (
            <li key={d.id}>
              <div className="doc-row">
                <span className={`tag ${d.kind}`}>{d.kind === 'sop' ? 'SOP' : 'Knowledge'}</span>
                <button className="link" onClick={() => view(d)}>
                  {d.title}
                </button>
                <span className="muted small-text">{d.chars.toLocaleString()} chars</span>
                <button className="link danger" onClick={() => remove(d)}>
                  Delete
                </button>
              </div>
              {open?.id === d.id && (
                <div className="doc-preview">
                  <Markdown text={open.content} />
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      <form onSubmit={add} className="card form">
        <strong>Add a document</strong>
        <div className="row">
          <label>
            Type
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="sop">SOP: a procedure to follow</option>
              <option value="knowledge">Knowledge: facts and context</option>
            </select>
          </label>
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Refund SOP" />
          </label>
        </div>
        <label>
          Content <span className="muted">(paste text, or load a .md / .txt file)</span>
          <textarea rows={6} value={content} onChange={(e) => setContent(e.target.value)} />
        </label>
        <input type="file" accept=".md,.txt,.markdown,text/plain,text/markdown" onChange={loadFile} />
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={!title.trim() || !content.trim()}>
          Add to library
        </button>
      </form>
    </div>
  )
}

function NewRunForm({ biz }) {
  const [idea, setIdea] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const run = await api.createRun(biz.id, idea)
      window.location.hash = `#/run/${run.id}`
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="card form">
      <label>
        What should the team work on?
        <textarea
          rows={4}
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="e.g. Plan the launch of a premium tier for tech startups, or: Reduce churn among our monthly customers."
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button className="primary" disabled={busy || idea.trim().length < 10}>
        {busy ? 'Starting…' : 'Send to the team →'}
      </button>
    </form>
  )
}

export default function BusinessView({ businessId }) {
  const [biz, setBiz] = useState(null)
  const [runs, setRuns] = useState([])
  const [error, setError] = useState('')

  const load = () => api.business(businessId).then(setBiz).catch((e) => setError(e.message))

  useEffect(() => {
    load()
    api.runs(businessId).then(setRuns).catch(() => {})
  }, [businessId])

  async function exportProfile() {
    const profile = await api.exportBusiness(businessId)
    const slug = biz.name.toLowerCase().replace(/\W+/g, '-')
    saveFile(`${slug}-profile.json`, JSON.stringify(profile, null, 2), 'application/json')
  }

  async function remove() {
    if (!confirm(`Delete ${biz.name}, its library and all its runs? This can't be undone.`)) return
    try {
      await api.deleteBusiness(businessId)
      window.location.hash = '#/'
    } catch (err) {
      setError(err.message)
    }
  }

  if (error) return <p className="error">{error}</p>
  if (!biz) return <p className="muted center">Loading…</p>

  return (
    <div className="business">
      <a href="#/" className="muted back">
        ← Command center
      </a>
      <div className="run-head">
        <h1>{biz.name}</h1>
        <div className="actions">
          <button onClick={exportProfile}>Export profile</button>
          <button className="danger" onClick={remove}>
            Delete
          </button>
        </div>
      </div>

      <section>
        <h2>New run</h2>
        <NewRunForm biz={biz} />
      </section>

      <section>
        <h2>Profile</h2>
        <Profile key={`${biz.name}|${biz.description}`} biz={biz} onSaved={load} />
      </section>

      <section>
        <h2>SOP & knowledge library</h2>
        <Library biz={biz} onChanged={load} />
      </section>

      {runs.length > 0 && (
        <section>
          <h2>Runs</h2>
          <RunList runs={runs} />
        </section>
      )}
    </div>
  )
}
