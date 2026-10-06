import { useEffect, useState } from 'react'
import { api } from './api.js'
import NewRun from './NewRun.jsx'
import RunView from './RunView.jsx'

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const match = hash.match(/^#\/run\/([a-f0-9]+)/)
  return match ? match[1] : null
}

export default function App() {
  const runId = useHashRoute()
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }))
  }, [])

  return (
    <div className="shell">
      <header className="topbar">
        <a href="#/" className="brand">
          <span className="logo">◆</span> VentureDesk
        </a>
        <span className="tagline">Your AI launch team</span>
        {health && (
          <span className={`pill ${health.ok ? (health.demo ? 'warn' : 'ok') : 'bad'}`}>
            {!health.ok ? 'Backend offline' : health.demo ? 'Demo mode' : health.model}
          </span>
        )}
      </header>
      <main>{runId ? <RunView key={runId} runId={runId} /> : <NewRun />}</main>
    </div>
  )
}
