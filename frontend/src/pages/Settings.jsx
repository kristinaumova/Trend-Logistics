import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { api } from '../api'

export default function Settings() {
  const { user } = useAuth()
  const [config, setConfig] = useState(null)

  useEffect(() => {
    api.getPublicConfig().then(setConfig).catch(() => setConfig({}))
  }, [])

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Управление пользователями и настройки системы</h1>
      </div>

      <section className="card settings-section">
        <h2 className="settings-section-title">Управление пользователями</h2>
        <p className="settings-desc">Учётные записи и роли. Функционал для расширения.</p>
        <div className="settings-current-user">
          <h3>Текущий пользователь</h3>
          <dl className="settings-dl">
            <dt>Логин</dt>
            <dd><strong>{user?.login ?? '—'}</strong></dd>
            <dt>Роль</dt>
            <dd>{user?.role ?? '—'}</dd>
          </dl>
        </div>
        <div className="settings-placeholder">
          <p>Список пользователей (добавление, редактирование, роли) — для расширения. Требуется API и права администратора.</p>
        </div>
      </section>

      <section className="card settings-section">
        <h2 className="settings-section-title">Настройки системы</h2>
        <p className="settings-desc">Параметры приложения и интеграций.</p>
        <dl className="settings-dl settings-system-dl">
          <dt>Ссылка на мониторинг (Grafana)</dt>
          <dd>
            <a href={config?.monitoring_url || '/grafana/'} target="_blank" rel="noopener noreferrer">
              {config?.monitoring_url || '/grafana/'}
            </a>
          </dd>
          <dt>Сервис внешних данных</dt>
          <dd><span className="muted">URL задаётся в переменных окружения backend (EXTERNAL_DATA_SERVICE_URL). Изменение — для расширения.</span></dd>
          <dt>JWT и безопасность</dt>
          <dd><span className="muted">Настройки задаются в .env (JWT_SECRET, JWT_EXPIRE). Редактирование — для расширения.</span></dd>
        </dl>
        <div className="settings-placeholder">
          <p>Редактирование настроек из интерфейса — для расширения (админ-API и хранение в БД или конфиге).</p>
        </div>
      </section>
    </div>
  )
}
