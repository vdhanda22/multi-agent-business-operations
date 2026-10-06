async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  team: () => request('/team'),
  runs: () => request('/runs'),
  createRun: (idea, company) => request('/runs', { method: 'POST', body: JSON.stringify({ idea, company }) }),
  revise: (id, feedback) => request(`/runs/${id}/revise`, { method: 'POST', body: JSON.stringify({ feedback }) }),
  approve: (id) => request(`/runs/${id}/approve`, { method: 'POST' }),
  events: (id) => new EventSource(`/api/runs/${id}/events`),
}
