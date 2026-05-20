import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

export default function AddressInput({ value, onChange, placeholder, required, id }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [hint, setHint] = useState('')
  const wrapRef = useRef(null)
  const debounceRef = useRef(null)

  useEffect(() => {
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  useEffect(() => {
    const q = (value || '').trim()
    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (q.length < 2) {
      setItems([])
      setHint('')
      setLoading(false)
      return
    }

    setLoading(true)
    setHint('')

    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.suggestAddress(q)
        const merged = (res.items || [])
          .filter((it) => it.type === 'address' || it.type === 'city')
          .map((it) => ({
            label: it.label || it.value,
            value: it.value,
            type: it.type,
          }))
        setItems(merged)
        setHint(merged.length === 0 ? 'Выберите адрес из списка подсказок' : '')
      } catch {
        setItems([])
        setHint('Не удалось загрузить адреса — проверьте подключение к серверу')
      } finally {
        setLoading(false)
      }
    }, 280)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [value])

  const pick = (item) => {
    onChange(item.value)
    setOpen(false)
    setHint('')
  }

  return (
    <div className="address-input-wrap" ref={wrapRef}>
      <input
        id={id}
        type="text"
        className="address-input"
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setOpen(false)
        }}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        maxLength={512}
      />
      {open && items.length > 0 && (
        <ul className="address-suggest-list" role="listbox">
          {items.map((item) => (
            <li key={`${item.type}-${item.value}`}>
              <button
                type="button"
                className="address-suggest-item"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(item)}
              >
                <span className="address-suggest-label">{item.label}</span>
                {item.type === 'city' && <span className="address-suggest-tag">город</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
      {open && loading && <p className="address-suggest-loading muted small">Поиск…</p>}
      {!loading && hint && <p className="address-suggest-hint muted small">{hint}</p>}
    </div>
  )
}
