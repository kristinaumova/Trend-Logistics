import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import CreateShipmentForm from '../components/CreateShipmentForm'

const statusLabels = {
  pending: 'Ожидает',
  in_transit: 'В пути',
  delivered: 'Доставлено',
  delayed: 'Задержано',
  cancelled: 'Отменено',
}

const transportLabels = {
  truck: 'Фура',
  rail: 'Поезд',
  sea: 'Море',
  air: 'Авиа',
}

const PERIODS = [
  { key: 'day', label: 'День' },
  { key: 'week', label: 'Неделя' },
  { key: 'month', label: 'Месяц' },
]

function formatEta(hours) {
  if (hours == null) return '—'
  if (hours < 1) return '< 1 ч'
  const h = Math.round(hours)
  if (h === 1) return '1 час'
  if (h < 5) return `${h} часа`
  return `${h} часов`
}

function Pagination({ currentPage, totalPages, total, limit, onPage }) {
  const items = []
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) items.push(i)
  } else {
    items.push(1)
    if (currentPage > 3) items.push('...')
    for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) {
      if (!items.includes(i)) items.push(i)
    }
    if (currentPage < totalPages - 2) items.push('...')
    if (totalPages > 1) items.push(totalPages)
  }
  return (
    <div className="pagination">
      {items.map((p, idx) =>
        p === '...' ? (
          <span key={`ellipsis-${idx}`} className="pagination-ellipsis">…</span>
        ) : (
          <button
            key={p}
            type="button"
            className={`pagination-btn ${p === currentPage ? 'active' : ''}`}
            onClick={() => onPage(p)}
          >
            {p}
          </button>
        )
      )}
      <span className="pagination-info">
        {((currentPage - 1) * limit) + 1}–{Math.min(currentPage * limit, total)} из {total}
      </span>
    </div>
  )
}

export default function Dashboard() {
  const [shipments, setShipments] = useState([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState(null)
  const [planFulfillment, setPlanFulfillment] = useState(null)
  const [activeShipments, setActiveShipments] = useState([])
  const [activeUpdatedAt, setActiveUpdatedAt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [planPeriod, setPlanPeriod] = useState('month')
  const [filters, setFilters] = useState({ skip: 0, limit: 10, status: '', transport_type: '' })
  const [showCreate, setShowCreate] = useState(false)
  const [listError, setListError] = useState(null)

  const currentPage = Math.floor(filters.skip / filters.limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / filters.limit))

  const loadMain = useCallback(async () => {
    setLoading(true)
    setListError(null)
    try {
      const listRes = await api.getShipments(filters)
      setShipments(listRes.items || [])
      setTotal(listRes.total ?? 0)
    } catch (e) {
      setShipments([])
      setTotal(0)
      setListError(e.message || 'Ошибка загрузки списка')
      console.error('Список поставок:', e)
    } finally {
      setLoading(false)
    }
    try {
      const statsRes = await api.getStats(planPeriod)
      setStats(statsRes)
      setPlanFulfillment(statsRes?.plan_fulfillment || null)
    } catch (e) {
      console.error('Статистика:', e)
      try {
        const statsRes = await api.getStats()
        setStats(statsRes)
      } catch {
        setStats(null)
      }
      setPlanFulfillment(null)
    }
  }, [filters.skip, filters.limit, filters.status, filters.transport_type, planPeriod])

  const loadActive = useCallback(async () => {
    try {
      const res = await api.getActiveShipments(10)
      setActiveShipments(res.items || [])
      setActiveUpdatedAt(new Date())
    } catch {
      setActiveShipments([])
    }
  }, [])

  useEffect(() => {
    let c = false
    loadMain().then(() => { if (!c) {} })
    return () => { c = true }
  }, [loadMain])

  useEffect(() => {
    loadActive()
    const t = setInterval(loadActive, 30000)
    return () => clearInterval(t)
  }, [loadActive])

  const onPage = (page) => {
    setFilters((f) => ({ ...f, skip: (page - 1) * f.limit }))
  }

  return (
    <>
      <div className="page-header page-header-row">
        <h1>Управление поставками</h1>
        <button type="button" className="primary" onClick={() => setShowCreate((v) => !v)}>
          {showCreate ? 'Скрыть форму' : '+ Новая поставка'}
        </button>
      </div>

      {showCreate && (
        <div className="card create-shipment-card">
          <h3 className="card-title">Новая поставка</h3>
          <CreateShipmentForm
            onCreated={() => {
              setShowCreate(false)
              loadMain()
              loadActive()
            }}
            onCancel={() => setShowCreate(false)}
          />
        </div>
      )}

      <div className="filters filters-bar">
        <label>Статус:</label>
        <select
          value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value, skip: 0 }))}
        >
          <option value="">Все</option>
          {Object.entries(statusLabels).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <label>Транспорт:</label>
        <select
          value={filters.transport_type}
          onChange={(e) => setFilters((f) => ({ ...f, transport_type: e.target.value, skip: 0 }))}
        >
          <option value="">Все</option>
          {Object.entries(transportLabels).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      <div className="card table-wrap dashboard-table-card">
        {loading ? (
          <p>Загрузка...</p>
        ) : listError ? (
          <p className="dashboard-list-error">
            {listError}. Обновите страницу (Ctrl+Shift+R). Если не помогло — пересоберите backend и frontend.
          </p>
        ) : shipments.length === 0 && (stats?.total_shipments ?? total) === 0 ? (
          <p>Нет поставок. Нажмите «+ Новая поставка» или дождитесь демо-данных при первом запуске сервера.</p>
        ) : shipments.length === 0 ? (
          <p className="dashboard-list-error">
            В базе {(stats?.total_shipments ?? total)} поставок, но список не загрузился. Пересоберите backend:{' '}
            <code>docker compose build backend &amp;&amp; docker compose up -d backend frontend</code>
          </p>
        ) : (
          <>
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Маршрут</th>
                  <th>Транспорт</th>
                  <th>План</th>
                  <th>Осталось / факт</th>
                  <th>Статус</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {shipments.map((s) => (
                  <tr key={s.id}>
                    <td>#{s.id}</td>
                    <td>{s.route_origin} – {s.route_destination}</td>
                    <td>{transportLabels[s.transport_type] || s.transport_type}</td>
                    <td>{s.planned_delivery_at ? new Date(s.planned_delivery_at).toLocaleDateString('ru') : '—'}</td>
                    <td>
                      {s.status === 'delivered'
                        ? (s.actual_delivery_at
                          ? `Доставлено ${new Date(s.actual_delivery_at).toLocaleDateString('ru')}`
                          : 'Доставлено')
                        : s.status === 'in_transit' || s.status === 'delayed'
                          ? 'см. карточку (от груза)'
                          : '—'}
                    </td>
                    <td><span className={`badge ${s.status}`}>{statusLabels[s.status] || s.status}</span></td>
                    <td>
                      <Link to={`/shipments/${s.id}`}>Открыть</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {total > filters.limit && (
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                total={total}
                limit={filters.limit}
                onPage={onPage}
              />
            )}
          </>
        )}
      </div>

      <p className="dashboard-footer-text">
        База данных содержит {stats?.total_shipments ?? 0} записей о поставках за 2024–2025 годы.
      </p>

      <div className="dashboard-cards">
        <div className="card dashboard-card plan-card">
          <h3 className="dashboard-card-title">Выполнение плана поставок</h3>
          <div className="plan-period-toggles">
            {PERIODS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                className={`period-toggle ${planPeriod === key ? 'active' : ''}`}
                onClick={() => setPlanPeriod(key)}
              >
                {label}
              </button>
            ))}
          </div>
          {planFulfillment ? (
            <>
              <p className="plan-percent">{planFulfillment.percent}%</p>
              <p className="plan-label">Выполнение плана</p>
              {planFulfillment.trend_percent !== 0 && (
                <p className={`plan-trend ${planFulfillment.trend_percent >= 0 ? 'up' : 'down'}`}>
                  {planFulfillment.trend_percent >= 0 ? '↑' : '↓'}
                  {Math.abs(planFulfillment.trend_percent)}% к прошлому периоду
                </p>
              )}
              <div className="plan-progress-wrap">
                <div
                  className="plan-progress-bar"
                  style={{ width: `${Math.min(100, planFulfillment.percent)}%` }}
                />
              </div>
              <div className="plan-stats-grid">
                <div className="plan-stat"><span className="plan-stat-value">{planFulfillment.plan}</span> <span className="plan-stat-label">План</span></div>
                <div className="plan-stat"><span className="plan-stat-value">{planFulfillment.fact}</span> <span className="plan-stat-label">Факт</span></div>
                <div className="plan-stat"><span className="plan-stat-value">{planFulfillment.in_work}</span> <span className="plan-stat-label">В работе</span></div>
                <div className="plan-stat"><span className="plan-stat-value">{planFulfillment.delayed}</span> <span className="plan-stat-label">Задержано</span></div>
              </div>
              <p className="plan-stat-suffix">поставки</p>
            </>
          ) : (
            <p className="muted">Загрузка…</p>
          )}
        </div>

        <div className="card dashboard-card realtime-card">
          <div className="realtime-header">
            <span className="realtime-active">Активные: {activeShipments.length}</span>
            <span className="realtime-updated">
              Обновлено: {activeUpdatedAt ? activeUpdatedAt.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' }) : '—'}
            </span>
          </div>
          <ul className="realtime-list">
            {activeShipments.length === 0 ? (
              <li className="realtime-item empty">Нет активных поставок</li>
            ) : (
              activeShipments.map((a) => (
                <li key={a.id} className="realtime-item">
                  <span className="realtime-dot" />
                  <Link to={`/shipments/${a.id}`} className="realtime-route">
                    {a.route_origin} – {a.route_destination}
                  </Link>
                  <Link to={`/shipments/${a.id}`} className="realtime-id">#{a.id}</Link>
                  <span className="realtime-transport">{transportLabels[a.transport_type] || a.transport_type}</span>
                  <span className="realtime-eta">ЕТА: {formatEta(a.eta_hours)}</span>
                  {a.telemetry_progress != null && (
                    <div
                      className="realtime-progress-mini"
                      title={`прогресс ${Math.round(a.telemetry_progress * 100)}%`}
                      style={{ width: `${Math.max(8, Math.round(a.telemetry_progress * 100))}%` }}
                    />
                  )}
                </li>
              ))
            )}
          </ul>
          <p className="realtime-footer">Обновляется каждые 30 секунд</p>
        </div>
      </div>
    </>
  )
}
