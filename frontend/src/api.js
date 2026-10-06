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

const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body ?? {}) })

export const api = {
  health: () => request('/health'),
  team: () => request('/team'),

  businesses: () => request('/businesses'),
  business: (id) => request(`/businesses/${id}`),
  createBusiness: (name, description) => post('/businesses', { name, description }),
  updateBusiness: (id, name, description) =>
    request(`/businesses/${id}`, { method: 'PUT', body: JSON.stringify({ name, description }) }),
  deleteBusiness: (id) => request(`/businesses/${id}`, { method: 'DELETE' }),
  exportBusiness: (id) => request(`/businesses/${id}/export`),
  importBusiness: (profile) => post('/businesses/import', profile),

  addDocument: (businessId, doc) => post(`/businesses/${businessId}/documents`, doc),
  document: (id) => request(`/documents/${id}`),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),

  runs: (businessId) => request(businessId ? `/runs?business_id=${businessId}` : '/runs'),
  createRun: (businessId, idea) => post('/runs', { business_id: businessId, idea }),
  revise: (id, feedback) => post(`/runs/${id}/revise`, { feedback }),
  approve: (id) => post(`/runs/${id}/approve`),
  events: (id) => new EventSource(`/api/runs/${id}/events`),
}
