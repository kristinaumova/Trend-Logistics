import { useEffect, useState, useCallback } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
  Line,
  ComposedChart,
  Area,
} from 'recharts'
import { api } from '../api'

const COLORS = ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#8b949e', '#a371f7']
const PERIODS = [
  { key: 'day', label: 'День' },
  { key: 'week', label: 'Неделя' },
  { key: 'month', label: 'Месяц' },
]

const STATUS_LABELS = {
  pending: 'Ожидает',
  in_transit: 'В пути',
  delivered: 'Доставлено',
  delayed: 'Задержано',
  cancelled: 'Отменено',
}

const TRANSPORT_LABELS = {
  truck: 'Авто',
  rail: 'Ж/д',
  sea: 'Море',
  air: 'Авиа',
}

const PRIORITY_LABELS = {
  low: 'Низкий',
  normal: 'Стандарт',
  high: 'Высокий',
}

const tooltipStyle = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
}

export default function Analytics() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [period, setPeriod] = useState('month')
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    setErr(null)
    api
      .getAnalyticsSummary(period)
      .then(setData)
      .catch((e) => setErr(e.message || 'Ошибка загрузки'))
      .finally(() => setLoading(false))
  }, [period])

  useEffect(() => {
    load()
  }, [load])

  if (err) {
    return (
      <div className="card">
        <p className="text-danger">{err}</p>
      </div>
    )
  }

  if (loading || !data) {
    return <p className="page-loading">Загрузка аналитики…</p>
  }

  const statusData = Object.entries(data.by_status || {})
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ name: STATUS_LABELS[k] || k, value: v }))

  const transportData = Object.entries(data.by_transport || {}).map(([k, v]) => ({
    name: TRANSPORT_LABELS[k] || k,
    shipments: v,
    forecasts: data.forecasts_by_transport?.[k] || 0,
  }))

  const priorityData = Object.entries(data.by_priority || {}).map(([k, v]) => ({
    name: PRIORITY_LABELS[k] || k,
    count: v,
  }))

  const riskData = (data.risk_distribution || []).filter((r) => r.count > 0)
  const factorData = (data.factor_impact_avg || []).map((f) => ({
    name: f.label || f.factor,
    hours: f.avg_hours,
  }))
  const timeline = data.forecasts_timeline || []
  const plan = data.plan_fulfillment
  const delivery = data.delivery_performance || {}
  const fs = data.forecast_stats || {}

  return (
    <div className="analytics-page">
      <div className="page-header analytics-page-header">
        <div>
          <h1>Аналитика</h1>
          <p className="page-lead">Сводка по поставкам, срокам и маршрутам</p>
        </div>
        <div className="plan-period-toggles">
          {PERIODS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={`period-toggle ${period === key ? 'active' : ''}`}
              onClick={() => setPeriod(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="analytics-kpi-grid">
        <div className="card kpi-card">
          <span className="kpi-label">Всего поставок</span>
          <span className="kpi-value">{data.total_shipments}</span>
        </div>
        <div className="card kpi-card">
          <span className="kpi-label">В пути / задержано</span>
          <span className="kpi-value">{data.active_shipments}</span>
        </div>
        <div className="card kpi-card">
          <span className="kpi-label">Доставлено</span>
          <span className="kpi-value kpi-success">{data.delivered_shipments}</span>
        </div>
        <div className="card kpi-card">
          <span className="kpi-label">Прогнозов</span>
          <span className="kpi-value">{data.forecasts_total}</span>
          <span className="kpi-sub">охват {data.forecast_coverage_percent}%</span>
        </div>
        <div className="card kpi-card">
          <span className="kpi-label">Средний срок (медиана)</span>
          <span className="kpi-value">{fs.avg_median_days} дн.</span>
          <span className="kpi-sub">
            {fs.min_median_days}–{fs.max_median_days} дн.
          </span>
        </div>
        <div className="card kpi-card">
          <span className="kpi-label">Средний риск срока</span>
          <span className="kpi-value">{(fs.avg_risk_score * 100).toFixed(0)}%</span>
          <span className="kpi-sub">высокий риск: {fs.high_risk_count}</span>
        </div>
        <div className="card kpi-card">
          <span className="kpi-label">В срок (доставленные)</span>
          <span className="kpi-value">
            {delivery.on_time_percent != null ? `${delivery.on_time_percent}%` : '—'}
          </span>
          <span className="kpi-sub">выборка {delivery.sample_size || 0}</span>
        </div>
        <div className="card kpi-card">
          <span className="kpi-label">Ср. задержка</span>
          <span className="kpi-value kpi-warn">
            {delivery.avg_delay_days != null ? `${delivery.avg_delay_days} дн.` : '—'}
          </span>
          <span className="kpi-sub">опозданий: {delivery.late_count || 0}</span>
        </div>
      </div>

      {plan && (
        <div className="card analytics-plan-card">
          <h3>Выполнение плана поставок</h3>
          <div className="analytics-plan-body">
            <div className="analytics-plan-main">
              <span className="analytics-plan-percent">{plan.percent}%</span>
              <span className="muted">план vs факт за период</span>
              {plan.trend_percent !== 0 && (
                <span className={`plan-trend ${plan.trend_percent >= 0 ? 'up' : 'down'}`}>
                  {plan.trend_percent >= 0 ? '↑' : '↓'} {Math.abs(plan.trend_percent)}% к прошлому
                </span>
              )}
              <div className="plan-progress-wrap analytics-plan-bar">
                <div
                  className="plan-progress-bar"
                  style={{ width: `${Math.min(100, plan.percent)}%` }}
                />
              </div>
            </div>
            <div className="analytics-plan-stats">
              <div><strong>{plan.plan}</strong><span className="muted"> план</span></div>
              <div><strong>{plan.fact}</strong><span className="muted"> факт</span></div>
              <div><strong>{plan.in_work}</strong><span className="muted"> в работе</span></div>
              <div><strong>{plan.delayed}</strong><span className="muted"> задержано</span></div>
            </div>
          </div>
        </div>
      )}

      <div className="analytics-charts-grid">
        <div className="card chart-card">
          <h3>Статусы поставок</h3>
          <div className="chart-wrap">
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={88} label>
                    {statusData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="muted chart-empty">Нет данных</p>
            )}
          </div>
        </div>

        <div className="card chart-card">
          <h3>Распределение риска прогнозов</h3>
          <div className="chart-wrap">
            {riskData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={riskData} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" stroke="var(--muted)" />
                  <YAxis type="category" dataKey="bucket" width={120} stroke="var(--muted)" tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="count" fill="#f85149" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="muted chart-empty">Создайте прогнозы для анализа риска</p>
            )}
          </div>
        </div>

        <div className="card chart-card">
          <h3>Транспорт: поставки и прогнозы</h3>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={transportData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="name" stroke="var(--muted)" />
                <YAxis stroke="var(--muted)" />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Bar dataKey="shipments" name="Поставки" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="forecasts" name="Прогнозы" fill="#3fb950" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card chart-card">
          <h3>Приоритет грузов</h3>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie
                  data={priorityData}
                  dataKey="count"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={88}
                  label
                >
                  {priorityData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card chart-card analytics-full-width">
        <h3>Динамика расчёта прогнозов (по неделям)</h3>
        <div className="chart-wrap chart-wrap-tall">
          {timeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={timeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="period" stroke="var(--muted)" />
                <YAxis stroke="var(--muted)" allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="count" fill="rgba(88,166,255,0.15)" stroke="none" />
                <Line type="monotone" dataKey="count" name="Прогнозов" stroke="var(--accent)" strokeWidth={2} dot />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <p className="muted chart-empty">Пока нет прогнозов за последние 90 дней</p>
          )}
        </div>
      </div>

      <div className="analytics-charts-grid">
        <div className="card chart-card">
          <h3>Влияние внешних факторов на срок (ср. часы)</h3>
          <div className="chart-wrap">
            {factorData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={factorData} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" stroke="var(--muted)" unit=" ч" />
                  <YAxis type="category" dataKey="name" width={100} stroke="var(--muted)" />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} ч`, 'Задержка']} />
                  <Bar dataKey="hours" fill="#d29922" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="muted chart-empty">Нет сохранённых факторов в прогнозах</p>
            )}
          </div>
        </div>

        <div className="card chart-card">
          <h3>Топ маршрутов по числу поставок</h3>
          <div className="analytics-routes-table-wrap">
            {(data.top_routes || []).length > 0 ? (
              <table className="analytics-routes-table">
                <thead>
                  <tr>
                    <th>Откуда</th>
                    <th>Куда</th>
                    <th>Поставок</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_routes.map((r, i) => (
                    <tr key={i}>
                      <td>{r.origin}</td>
                      <td>{r.destination}</td>
                      <td><strong>{r.count}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted chart-empty">Нет маршрутов</p>
            )}
          </div>
          {data.cargo_stats && (
            <p className="muted small analytics-cargo-note">
              Средний вес груза: {data.cargo_stats.avg_weight_kg} кг · суммарно:{' '}
              {data.cargo_stats.total_weight_kg.toLocaleString('ru')} кг
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
