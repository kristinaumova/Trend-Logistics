import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api'
import RouteMap from '../components/RouteMap'
import { getTransportMeta } from '../constants/transport'

const statusLabels = {
  pending: 'Запланирована',
  in_transit: 'В пути',
  delivered: 'Завершена',
  delayed: 'Задержано',
  cancelled: 'Отменено',
}

const transportLabels = {
  truck: 'Фура',
  rail: 'Поезд',
  sea: 'Море',
  air: 'Авиа',
}

const priorityLabels = {
  low: 'Низкий',
  normal: 'Стандартный',
  high: 'Высокий',
}

function buildFactorInsights(factors) {
  if (!factors) return []
  const w = factors.weather
  const t = factors.traffic
  const g = factors.geopolitics
  const cond = w?.condition
  const weatherRisk = (w?.impact_delay_hours ?? 0) >= 4 || ['snow', 'fog'].includes(cond)
  const trafficRisk = t?.congestion_level === 'high' || (t?.impact_delay_hours ?? 0) >= 4
  const roadWorks = (t?.road_works_km ?? 0) > 8
  const geoRisk = (g?.impact_delay_hours ?? 0) > 8 || g?.risk_level === 'high'
  return [
    {
      title: 'Погода',
      detail: `${cond || '—'} · задержка ${(w?.impact_delay_hours ?? 0).toFixed(1)} ч`,
      tone: weatherRisk ? 'warn' : 'ok',
    },
    {
      title: 'Трафик и дороги',
      detail: `загрузка ${t?.congestion_level || '—'} · ремонт ${(t?.road_works_km ?? 0).toFixed(1)} км · +${(t?.impact_delay_hours ?? 0).toFixed(1)} ч`,
      tone: trafficRisk || roadWorks ? 'warn' : 'ok',
    },
    {
      title: 'Коридор',
      detail: `риск ${g?.risk_level || '—'} · +${(g?.impact_delay_hours ?? 0).toFixed(1)} ч`,
      tone: geoRisk ? 'warn' : 'ok',
    },
  ]
}

function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getWeatherSummary(factors) {
  const w = factors?.weather
  if (!w) return 'Погода по маршруту уточняется.'
  const cond = w.condition
  const condRu = { clear: 'Ясно', moderate_rain: 'Небольшие осадки', snow: 'Снег', fog: 'Туман', cloudy: 'Облачно' }[cond] || cond
  return `${condRu}, ветер до ${w.wind_speed_kmh ?? 0} км/ч. Оценка влияния на срок: +${(w.impact_delay_hours ?? 0).toFixed(1)} ч.`
}

export default function ShipmentDetail() {
  const { id } = useParams()
  const [shipment, setShipment] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [factors, setFactors] = useState(null)
  const [routeData, setRouteData] = useState(null)
  const [telemetry, setTelemetry] = useState(null)
  const [loading, setLoading] = useState(true)
  const [forecastLoading, setForecastLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [completionStatus, setCompletionStatus] = useState(null)
  const [actionMessage, setActionMessage] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const s = await api.getShipment(id)
        if (!cancelled) setShipment(s)
        const [fc, fac, route, tel] = await Promise.all([
          api.getForecastByShipment(id).catch(() => null),
          s ? api.getFactors(s.route_origin, s.route_destination).catch(() => null) : Promise.resolve(null),
          s ? api.getRoute(s.route_origin, s.route_destination, s.transport_type).catch(() => null) : Promise.resolve(null),
          s ? api.getTelemetry(s.id).catch(() => null) : Promise.resolve(null),
        ])
        if (!cancelled) {
          setForecast(fc)
          setFactors(fac)
          setRouteData(route)
          setTelemetry(tel)
        }
      } catch (e) {
        if (!cancelled) {
          setError(e.status === 404 ? 'Поставка не найдена' : e.message)
          setShipment(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [id])

  useEffect(() => {
    if (!shipment?.id) return
    if (!['in_transit', 'delayed'].includes(shipment.status)) {
      setCompletionStatus(null)
      return
    }
    let cancelled = false
    api.getCompletionStatus(shipment.id).then((s) => {
      if (!cancelled) setCompletionStatus(s)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [shipment?.id, shipment?.status])

  useEffect(() => {
    if (!shipment?.id) return
    if (!['in_transit', 'delayed'].includes(shipment.status)) return
    const poll = setInterval(async () => {
      try {
        const [tel, comp] = await Promise.all([
          api.getTelemetry(shipment.id),
          api.getCompletionStatus(shipment.id).catch(() => null),
        ])
        setTelemetry(tel)
        if (comp) setCompletionStatus(comp)
      } catch {
        /* ignore */
      }
    }, 12000)
    return () => clearInterval(poll)
  }, [shipment?.id, shipment?.status])

  const reloadShipment = async () => {
    const s = await api.getShipment(id)
    setShipment(s)
    const [fc, fac, route, tel] = await Promise.all([
      api.getForecastByShipment(id).catch(() => null),
      api.getFactors(s.route_origin, s.route_destination).catch(() => null),
      api.getRoute(s.route_origin, s.route_destination, s.transport_type).catch(() => null),
      api.getTelemetry(s.id).catch(() => null),
    ])
    setForecast(fc)
    setFactors(fac)
    setRouteData(route)
    setTelemetry(tel)
  }

  const handleStart = async () => {
    setActionLoading(true)
    setActionMessage(null)
    try {
      const res = await api.startShipment(Number(id))
      setShipment(res.shipment)
      setActionMessage('Поставка отправлена в путь.')
      await reloadShipment()
    } catch (e) {
      setActionMessage(e.message || 'Не удалось начать перевозку')
    } finally {
      setActionLoading(false)
    }
  }

  const handleComplete = async () => {
    setActionLoading(true)
    setActionMessage(null)
    try {
      const res = await api.completeShipment(Number(id))
      setShipment(res.shipment)
      setActionMessage('Поставка доставлена.')
      await reloadShipment()
    } catch (e) {
      setActionMessage(e.message || 'Не удалось завершить')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    const reason = window.prompt('Причина отмены (необязательно):')
    if (reason === null) return
    setActionLoading(true)
    setActionMessage(null)
    try {
      const res = await api.cancelShipment(Number(id), reason || null)
      setShipment(res.shipment)
      setActionMessage('Поставка отменена.')
      setCompletionStatus(null)
    } catch (e) {
      setActionMessage(e.message || 'Не удалось отменить')
    } finally {
      setActionLoading(false)
    }
  }

  const requestForecast = async () => {
    setForecastLoading(true)
    try {
      const fc = await api.createForecast(Number(id))
      setForecast(fc)
      if (shipment) {
        const fac = await api.getFactors(shipment.route_origin, shipment.route_destination)
        setFactors(fac)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setForecastLoading(false)
    }
  }

  if (loading) return <p className="page-loading">Загрузка...</p>
  if (error || !shipment) return <p>{error || 'Не найдено'}. <Link to="/">На дашборд</Link></p>

  const insights = buildFactorInsights(factors)
  const totalImpactHours = (forecast?.factors_impact || []).reduce((s, f) => s + (f.impact_hours || 0), 0)
  const medianDays = forecast ? forecast.predicted_days_median : null
  const medianHoursFromForecast = medianDays != null ? Math.round(medianDays * 24) : null
  const distanceKm = routeData?.distance_km ?? null
  const baseHours = routeData?.duration_hours ?? null
  const tmeta = getTransportMeta(shipment.transport_type)
  const telData = telemetry?.available ? telemetry?.data : null
  const trackingLive = telemetry?.live === true
  const isDelivered = shipment.status === 'delivered'
  const isCancelled = shipment.status === 'cancelled'
  const canStart = shipment.status === 'pending'
  const canComplete = ['in_transit', 'delayed'].includes(shipment.status)
  const canCancel = ['pending', 'in_transit', 'delayed'].includes(shipment.status)
  const nearDestination = completionStatus?.can_complete === true
  const delivery = shipment.delivery_summary
  const mapCoordinates = telData?.coordinates?.length > 1 ? telData.coordinates : routeData?.coordinates
  const cargoPosition = isDelivered
    ? routeData?.destination
      ? { lat: routeData.destination[0], lon: routeData.destination[1] }
      : telData?.position ?? null
    : telData?.position ?? null
  const remainingHours = trackingLive ? telData?.eta_hours_remaining : null
  const remainingKm = trackingLive ? telData?.remaining_km : null
  const cargoProgressPct =
    telData?.progress != null ? Math.round(telData.progress * 100) : null
  return (
    <>
      <div className="page-header page-header-row">
        <h1 style={{ margin: 0 }}>Детали поставки #{shipment.id}</h1>
        <Link to="/">← К списку</Link>
      </div>

      {(canStart || canComplete || canCancel) && (
        <div className="card shipment-actions-card full-width">
          <h3 className="card-title">
            {canStart ? 'Запуск перевозки' : 'Завершить или отменить'}
          </h3>
          {canStart && (
            <p className="completion-hint completion-hint--warn">
              Поставка запланирована. Нажмите «Начать перевозку», чтобы отправить груз в путь и включить отслеживание.
            </p>
          )}
          {canComplete && completionStatus && (
            <p className={`completion-hint ${nearDestination ? 'completion-hint--ok' : 'completion-hint--warn'}`}>
              {completionStatus.distance_km != null && (
                <>До пункта назначения ~{completionStatus.distance_km} км (нужно ≤ {completionStatus.max_distance_km} км или прогресс ≥ 88%). </>
              )}
              {nearDestination
                ? 'Груз у назначения — можно завершить доставку.'
                : 'Маршрут ещё не завершён — дождитесь прибытия груза или отмените поставку.'}
            </p>
          )}
          <div className="shipment-actions-row">
            {canStart && (
              <button
                type="button"
                className="primary btn-complete-ready"
                disabled={actionLoading}
                onClick={handleStart}
              >
                {actionLoading ? '…' : '▶ Начать перевозку'}
              </button>
            )}
            {canComplete && (
              <button
                type="button"
                className={nearDestination ? 'primary btn-complete-ready' : 'primary btn-complete-disabled'}
                disabled={actionLoading || !nearDestination}
                onClick={handleComplete}
              >
                {actionLoading ? '…' : '✓ Завершить доставку'}
              </button>
            )}
            {canCancel && (
              <button
                type="button"
                className={!nearDestination && canComplete ? 'btn-cancel-prominent' : 'btn-secondary'}
                disabled={actionLoading}
                onClick={handleCancel}
              >
                Отменить поставку
              </button>
            )}
          </div>
          {actionMessage && (
            <p className={`action-feedback ${actionMessage.includes('доставлена') || actionMessage.includes('отменена') || actionMessage.includes('в путь') ? 'action-feedback--ok' : 'action-feedback--err'}`}>
              {actionMessage}
            </p>
          )}
        </div>
      )}

      <div className="shipment-detail-grid">
        <div className="card card-details">
          <div className="card-title-row">
            <h3 className="card-title">Детали поставки</h3>
            <span className="shipment-id">#{shipment.id}</span>
          </div>
          <p className="detail-route-line">
            <strong>{shipment.route_origin}</strong>
            <span className="detail-route-arrow"> → </span>
            <strong>{shipment.route_destination}</strong>
          </p>
          <p className="muted small">
            Создана: {shipment.created_at ? new Date(shipment.created_at).toLocaleString('ru') : '—'}
            {shipment.planned_delivery_at && (
              <> · План: {new Date(shipment.planned_delivery_at).toLocaleDateString('ru')}</>
            )}
          </p>
          <p className="label">Статус</p>
          <div className="status-options">
            <span className={`status-option ${['pending', 'in_transit', 'delayed'].includes(shipment.status) ? 'active' : ''}`}>
              {statusLabels[shipment.status] || shipment.status}
            </span>
            <span className={`status-option ${shipment.status === 'delivered' ? 'active' : ''}`}>
              {shipment.actual_delivery_at
                ? `Завершена ${new Date(shipment.actual_delivery_at).toLocaleDateString('ru')}`
                : 'Не завершена'}
            </span>
          </div>
          {trackingLive && cargoProgressPct != null && (
            <p className="detail-live-hint muted small">
              Груз на маршруте ~{cargoProgressPct}%
            </p>
          )}
          {isCancelled && (
            <p className="muted small shipment-cancelled-note">Поставка отменена.</p>
          )}
          {isDelivered && delivery && (
            <div className="delivery-facts">
              <p className="label" style={{ marginTop: '1rem' }}>Факт доставки</p>
              {delivery.complete ? (
                <>
                  <p className="delivery-facts-duration">{delivery.duration_label}</p>
                  <p className="muted small delivery-facts-sub">реальное время в пути с грузом</p>
                  <dl className="delivery-facts-grid">
                    <div>
                      <dt>Начало рейса</dt>
                      <dd>{formatDateTime(delivery.transit_started_at)}</dd>
                    </div>
                    <div>
                      <dt>Доставлено</dt>
                      <dd>{formatDateTime(delivery.delivered_at)}</dd>
                    </div>
                    {delivery.vs_plan_label && (
                      <div className="delivery-facts-plan">
                        <dt>К плану</dt>
                        <dd>{delivery.vs_plan_label}</dd>
                      </div>
                    )}
                  </dl>
                </>
              ) : (
                <p className="muted small">{delivery.vs_plan_label || 'Укажите даты начала и завершения рейса.'}</p>
              )}
            </div>
          )}
        </div>

        <div className="card card-forecast">
          <h3 className="card-title">Прогноз доставки</h3>
          <div className="forecast-weather-info">
            <span className="forecast-weather-icon">☁</span>
            <span>{getWeatherSummary(factors)}</span>
          </div>
          <ul className="factor-insights">
            {insights.map((x) => (
              <li key={x.title} className={`factor-insight factor-insight--${x.tone}`}>
                <span className="factor-insight-title">{x.title}</span>
                <span className="factor-insight-detail">{x.detail}</span>
              </li>
            ))}
          </ul>
          {forecast ? (
            <>
              <div className="forecast-time">
                {medianDays != null ? (
                  <>
                    {medianDays < 1.5
                      ? `≈ ${medianHoursFromForecast} ч`
                      : `${medianDays.toFixed(1)} дн.`}
                  </>
                ) : (
                  '—'
                )}
              </div>
              <p className="forecast-subtitle forecast-subtitle-muted">
                Ориентировочный срок с учётом погоды и дорог. Неопределённость: {(forecast.risk_score * 100).toFixed(0)}%.
              </p>
            </>
          ) : (
            <p className="forecast-no-data">Прогноз не рассчитан</p>
          )}
          <button
            type="button"
            className="primary"
            disabled={forecastLoading}
            onClick={requestForecast}
            style={{ marginTop: '1rem' }}
          >
            {forecastLoading ? 'Расчёт…' : 'Рассчитать прогноз'}
          </button>
        </div>

        <div className="card card-params full-width">
          <h3 className="card-title">Параметры поставки</h3>
          <div className="params-grid">
            <div className="param"><span className="param-label">Откуда</span><span>{shipment.route_origin}</span></div>
            <div className="param"><span className="param-label">Куда</span><span>{shipment.route_destination}</span></div>
            <div className="param"><span className="param-label">Тип груза</span><span>{shipment.product_type}</span></div>
            <div className="param"><span className="param-label">Вес</span><span>{shipment.weight_kg != null ? `${Math.round(shipment.weight_kg)} кг` : '—'}</span></div>
            <div className="param"><span className="param-label">Объём</span><span>{shipment.volume_m3 != null ? `${shipment.volume_m3} м³` : '—'}</span></div>
            <div className="param"><span className="param-label">Приоритет</span><span>{priorityLabels[shipment.priority] || shipment.priority}</span></div>
          </div>
          <div className={`transport-badge transport-badge--${shipment.transport_type}`}>
            <span className="transport-icon" aria-hidden>{tmeta.icon}</span>
            <div>
              <div className="transport-title">{tmeta.title}</div>
              <div className="transport-sub muted">{tmeta.subtitle}</div>
              <div className="transport-short">{transportLabels[shipment.transport_type] || shipment.transport_type}</div>
            </div>
          </div>
        </div>

        {telData && (
          <div className="card card-telemetry full-width">
            <h3 className="card-title">Позиция груза</h3>
            {isDelivered && shipment.actual_delivery_at && (
              <p className="telemetry-delivered-fact">
                Доставлена: {new Date(shipment.actual_delivery_at).toLocaleString('ru')}
              </p>
            )}
            {trackingLive && (
              <>
                <div className="telemetry-row">
                  <span>Скорость</span>
                  <strong>{telData.speed_kmh} км/ч</strong>
                </div>
                <div className="telemetry-row">
                  <span>Пройдено маршрута</span>
                  <div className="telemetry-progress-wrap">
                    <div className="telemetry-progress" style={{ width: `${Math.round((telData.progress || 0) * 100)}%` }} />
                  </div>
                  <span>{Math.round((telData.progress || 0) * 100)}%</span>
                </div>
                <div className="telemetry-row">
                  <span>Осталось до назначения</span>
                  <strong>
                    {remainingKm != null ? `${remainingKm} км · ` : ''}
                    {remainingHours != null ? `${remainingHours} ч` : '—'}
                  </strong>
                </div>
              </>
            )}
            {cargoPosition && (
              <div className="telemetry-row">
                <span>{isDelivered ? 'Точка доставки' : 'Координаты груза'}</span>
                <strong>
                  {cargoPosition.lat.toFixed(4)}°, {cargoPosition.lon.toFixed(4)}°
                </strong>
              </div>
            )}
          </div>
        )}
        {telemetry && !telemetry.available && (
          <div className="card muted-card full-width">
            <p className="muted">Данные о позиции груза временно недоступны.</p>
          </div>
        )}

        <div className="card card-route full-width">
          <h3 className="card-title">Маршрут и условия</h3>
          {routeData?.source && routeData.source !== 'osrm' && (
            <p className="muted small" style={{ marginBottom: '0.5rem' }}>
              {routeData.source === 'estimated_osrm_corrected'
                ? 'Время маршрута уточнено по расстоянию (ответ OSRM был нетипичным).'
                : 'Маршрут по оценке расстояния между городами (OSRM недоступен).'}
            </p>
          )}
          <div className="route-map-wrap">
            {(mapCoordinates?.length || routeData?.origin || cargoPosition) ? (
              <RouteMap
                origin={routeData?.origin}
                destination={routeData?.destination}
                coordinates={mapCoordinates}
                cargoPosition={cargoPosition}
              />
            ) : (
              <div className="route-map-placeholder">
                <p>Карта маршрута {shipment.route_origin} → {shipment.route_destination}</p>
                <p className="muted">
                  {routeData?.error || 'Не удалось построить маршрут для указанных адресов.'}
                </p>
              </div>
            )}
          </div>
          <div className="route-summary-cards">
            <div className="route-summary-card">
              <span className="route-summary-value">{distanceKm != null ? `${distanceKm} км` : '—'}</span>
              <span className="route-summary-label">Расстояние</span>
            </div>
            <div className="route-summary-card">
              <span className="route-summary-value">
                {isDelivered && delivery?.duration_label
                  ? delivery.duration_label
                  : trackingLive && remainingHours != null
                    ? `${remainingHours} ч`
                    : baseHours != null
                      ? `${baseHours} ч`
                      : '—'}
              </span>
              <span className="route-summary-label">
                {isDelivered && delivery?.complete
                  ? 'Фактическое время доставки'
                  : trackingLive
                    ? 'Осталось до назначения (от груза)'
                    : 'Полный маршрут (отправление → назначение)'}
              </span>
            </div>
            <div className="route-summary-card">
              <span className="route-summary-value">+{Math.round(totalImpactHours)} ч</span>
              <span className="route-summary-label">Внешние факторы (сумма)</span>
            </div>
          </div>
          <div className="route-charts">
            <div className="route-chart-card">
              <h4>Погода</h4>
              <div className="chart-placeholder">
                {factors?.weather ? (
                  <p>Температура {(factors.weather.temp_min ?? factors.weather.temp_max ?? '—')}°C · {factors.weather.condition}</p>
                ) : (
                  <p>Нет данных</p>
                )}
              </div>
            </div>
            <div className="route-chart-card">
              <h4>Дороги</h4>
              <div className="chart-placeholder">
                {factors?.traffic ? (
                  <p>Загруженность {factors.traffic.congestion_level} · ремонт {factors.traffic.road_works_km ?? 0} км</p>
                ) : (
                  <p>Нет данных</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
