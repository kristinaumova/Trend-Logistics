const API = '/api'

function getAuthHeader() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...getAuthHeader(), ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text()
    let message = res.statusText
    let detail = null
    try {
      const j = JSON.parse(body)
      detail = j.detail ?? j
      if (typeof detail === 'string') message = detail
      else if (detail?.message) message = detail.message
      else if (Array.isArray(detail)) message = detail.map((x) => x.msg || x).join(', ')
    } catch {
      if (body) message = body
    }
    const err = new Error(message)
    err.status = res.status
    err.body = body
    err.detail = detail
    throw err
  }
  return res.json()
}

export const api = {
  getShipments(params = {}) {
    const clean = {}
    if (params.skip != null) clean.skip = params.skip
    if (params.limit != null) clean.limit = params.limit
    if (params.status) clean.status = params.status
    if (params.transport_type) clean.transport_type = params.transport_type
    if (params.route_origin) clean.route_origin = params.route_origin
    const q = new URLSearchParams(clean).toString()
    return request(`/shipments${q ? `?${q}` : ''}`)
  },
  getShipment(id) {
    return request(`/shipments/${id}`)
  },
  createShipment(data) {
    return request('/shipments', { method: 'POST', body: JSON.stringify(data) })
  },
  getStats(period) {
    const q = period ? `?period=${encodeURIComponent(period)}` : ''
    return request(`/shipments/stats${q}`)
  },
  getActiveShipments(limit = 20) {
    return request(`/shipments/active?limit=${limit}`)
  },
  createForecast(shipmentId) {
    return request('/forecasts', { method: 'POST', body: JSON.stringify({ shipment_id: shipmentId }) })
  },
  getForecastByShipment(shipmentId) {
    return request(`/forecasts/by-shipment/${shipmentId}`)
  },
  getFactors(routeOrigin, routeDestination) {
    return request(`/factors/for-route?route_origin=${encodeURIComponent(routeOrigin)}&route_destination=${encodeURIComponent(routeDestination)}`)
  },
  login(login, password) {
    return request('/auth/login', { method: 'POST', body: JSON.stringify({ login, password }) })
  },
  me() {
    return request('/auth/me')
  },
  getPublicConfig() {
    return request('/config/public')
  },
  getRoute(routeOrigin, routeDestination, transportType = 'truck') {
    const t = transportType ? `&transport_type=${encodeURIComponent(transportType)}` : ''
    return request(
      `/route?route_origin=${encodeURIComponent(routeOrigin)}&route_destination=${encodeURIComponent(routeDestination)}${t}`
    )
  },
  getAnalyticsSummary(period = 'month') {
    return request(`/analytics/summary?period=${encodeURIComponent(period)}`)
  },
  listUsers() {
    return request('/users')
  },
  createUser(payload) {
    return request('/users', { method: 'POST', body: JSON.stringify(payload) })
  },
  deleteUser(userId) {
    return request(`/users/${userId}`, { method: 'DELETE' })
  },
  getTelemetry(shipmentId) {
    return request(`/telemetry/shipment/${shipmentId}`)
  },
  getCompletionStatus(shipmentId) {
    return request(`/shipments/${shipmentId}/completion-status`)
  },
  startShipment(shipmentId) {
    return request(`/shipments/${shipmentId}/start`, { method: 'POST' })
  },
  completeShipment(shipmentId) {
    return request(`/shipments/${shipmentId}/complete`, { method: 'POST' })
  },
  cancelShipment(shipmentId, notes = null) {
    return request(`/shipments/${shipmentId}/cancel`, {
      method: 'POST',
      body: JSON.stringify(notes != null ? { notes } : {}),
    })
  },
  suggestAddress(q) {
    return request(`/geocode/suggest?q=${encodeURIComponent(q)}`)
  },
}
