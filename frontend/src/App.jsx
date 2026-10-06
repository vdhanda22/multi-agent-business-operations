import { useEffect, useState } from 'react'
import { api } from './api.js'
import BusinessView from './BusinessView.jsx'
import CommandCenter from './CommandCenter.jsx'
import RunView from './RunView.jsx'

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const match = hash.match(/^#\/(run|business)\/([a-f0-9]+)/)
  return match ? { page: match[1], id: match[2] } : { page: 'home' }
}

export default function App() {
  const route = useHashRoute()
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
        <span className="tagline">Multi-agent AI for business operations</span>
        {health && (
          <span className={`pill ${health.ok ? (health.demo ? 'warn' : 'ok') : 'bad'}`}>
            {!health.ok ? 'Backend offline' : health.demo ? 'Demo mode' : health.model}
          </span>
        )}
      </header>
      <main>
        {route.page === 'run' && <RunView key={route.id} runId={route.id} />}
        {route.page === 'business' && <BusinessView key={route.id} businessId={route.id} />}
        {route.page === 'home' && <CommandCenter />}
      </main>
    </div>
  )
}
