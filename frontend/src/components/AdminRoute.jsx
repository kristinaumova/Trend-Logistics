import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function AdminRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <p className="page-loading">Загрузка…</p>
  if (!user || user.role !== 'admin') return <Navigate to="/" replace />
  return children
}
