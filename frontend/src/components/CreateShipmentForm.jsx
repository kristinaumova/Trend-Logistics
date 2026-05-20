import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import AddressInput from './AddressInput'

const transportOptions = [
  { value: 'truck', label: 'Фура' },
  { value: 'rail', label: 'Поезд' },
  { value: 'sea', label: 'Море' },
  { value: 'air', label: 'Авиа' },
]

const defaultForm = {
  route_origin: 'Москва',
  route_destination: 'Санкт-Петербург',
  transport_type: 'truck',
  product_type: 'Генеральные грузы',
  weight_kg: '1200',
  volume_m3: '8',
  priority: 'normal',
  status: 'in_transit',
}

export default function CreateShipmentForm({ onCreated, onCancel }) {
  const navigate = useNavigate()
  const [form, setForm] = useState(defaultForm)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const setField = (key, val) => setForm((f) => ({ ...f, [key]: val }))

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (form.route_origin.trim() === form.route_destination.trim()) {
      setError('Пункт отправления и назначения должны отличаться')
      return
    }
    setSaving(true)
    try {
      const payload = {
        route_origin: form.route_origin.trim(),
        route_destination: form.route_destination.trim(),
        transport_type: form.transport_type,
        product_type: form.product_type.trim(),
        weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
        volume_m3: form.volume_m3 ? Number(form.volume_m3) : null,
        priority: form.priority,
        status: form.status,
      }
      const created = await api.createShipment(payload)
      onCreated?.(created)
      navigate(`/shipments/${created.id}`)
    } catch (err) {
      setError(err.message || 'Не удалось создать поставку')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="create-shipment-form" onSubmit={handleSubmit}>
      <p className="muted small create-shipment-hint">
        Начните вводить и выберите пункт из списка подсказок
      </p>
      <div className="form-grid">
        <label>
          Откуда
          <AddressInput
            value={form.route_origin}
            onChange={(v) => setField('route_origin', v)}
            placeholder="Начните вводить город или адрес"
            required
          />
        </label>
        <label>
          Куда
          <AddressInput
            value={form.route_destination}
            onChange={(v) => setField('route_destination', v)}
            placeholder="Начните вводить город или адрес"
            required
          />
        </label>
        <label>
          Транспорт
          <select value={form.transport_type} onChange={(e) => setField('transport_type', e.target.value)}>
            {transportOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label>
          Статус
          <select value={form.status} onChange={(e) => setField('status', e.target.value)}>
            <option value="pending">Запланирована</option>
            <option value="in_transit">В пути</option>
            <option value="delayed">Задержана</option>
          </select>
        </label>
        <label>
          Тип груза
          <input value={form.product_type} onChange={(e) => setField('product_type', e.target.value)} required />
        </label>
        <label>
          Приоритет
          <select value={form.priority} onChange={(e) => setField('priority', e.target.value)}>
            <option value="low">Низкий</option>
            <option value="normal">Стандартный</option>
            <option value="high">Высокий</option>
          </select>
        </label>
        <label>
          Вес, кг
          <input type="number" min="1" value={form.weight_kg} onChange={(e) => setField('weight_kg', e.target.value)} />
        </label>
        <label>
          Объём, м³
          <input type="number" min="0" step="0.1" value={form.volume_m3} onChange={(e) => setField('volume_m3', e.target.value)} />
        </label>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={saving}>
            Отмена
          </button>
        )}
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Создание…' : 'Создать поставку'}
        </button>
      </div>
    </form>
  )
}
