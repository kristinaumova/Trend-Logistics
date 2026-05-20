import { Link, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { api } from '../api'

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [config, setConfig] = useState({ monitoring_url: null })

  useEffect(() => {
    api.getPublicConfig().then(setConfig).catch(() => {})
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <>
      <header className="app-header">
        <div className="app-header-left">
          <Link to="/" className="brand">
            Trend Logistics
          </Link>
          <span className="brand-badge">Логистика</span>
        </div>
        <nav className="app-nav">
          <Link to="/">Главная</Link>
          <Link to="/analytics">Аналитика</Link>
          <a href={config.monitoring_url || '/grafana/'} target="_blank" rel="noopener noreferrer">
            Мониторинг
          </a>
          <Link to="/settings">Настройки</Link>
          {user?.role === 'admin' && <Link to="/admin" className="nav-admin">Админ</Link>}
        </nav>
        <div className="app-header-right">
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          {user && (
            <span className="user-menu">
              <span className="user-login">{user.login}</span>
              <span className="user-role">{user.role}</span>
              <button type="button" className="btn-logout" onClick={handleLogout}>
                Выход
              </button>
            </span>
          )}
        </div>
      </header>
      <main className="app-main">{children}</main>
    </>
  )
}
