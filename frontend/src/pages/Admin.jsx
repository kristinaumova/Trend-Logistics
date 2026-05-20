import { useEffect, useState } from 'react'
import { api } from '../api'

const ROLES = [
  { value: 'logistician', label: 'Логист' },
  { value: 'analyst', label: 'Аналитик' },
  { value: 'admin', label: 'Администратор' },
]

export default function Admin() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('logistician')
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    api.listUsers()
      .then(setUsers)
      .catch((e) => setError(e.message || 'Ошибка'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await api.createUser({ login, password, role })
      setLogin('')
      setPassword('')
      setRole('logistician')
      load()
    } catch (err) {
      setError(err.body || err.message || 'Не удалось создать')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (userId) => {
    if (!window.confirm('Удалить пользователя?')) return
    try {
      await api.deleteUser(userId)
      load()
    } catch (err) {
      setError(err.body || err.message)
    }
  }

  return (
    <div className="admin-page">
      <div className="page-header">
        <h1>Администрирование</h1>
        <p className="page-lead">Пользователи системы</p>
      </div>

      <div className="card admin-form-card">
        <h3>Новый пользователь</h3>
        <form onSubmit={handleCreate} className="admin-form">
          <label>
            Логин
            <input value={login} onChange={(e) => setLogin(e.target.value)} required minLength={2} />
          </label>
          <label>
            Пароль
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={4} />
          </label>
          <label>
            Роль
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="primary" disabled={saving}>{saving ? 'Создание…' : 'Создать'}</button>
        </form>
        {error && <p className="text-danger" style={{ marginTop: '1rem' }}>{error}</p>}
      </div>

      <div className="card">
        <h3>Список пользователей</h3>
        {loading ? (
          <p>Загрузка…</p>
        ) : (
          <div className="table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Логин</th>
                  <th>Роль</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.id}</td>
                    <td>{u.login}</td>
                    <td>{u.role}</td>
                    <td>
                      <button type="button" className="btn-danger-soft" onClick={() => handleDelete(u.id)}>
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
