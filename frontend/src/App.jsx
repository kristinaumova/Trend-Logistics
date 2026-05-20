import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ShipmentDetail from './pages/ShipmentDetail'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import Admin from './pages/Admin'

function ProtectedLayout({ children }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  )
}

function IfLoggedInRedirect({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <p className="page-loading">Загрузка…</p>
  if (user) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <div className="app">
          <Routes>
            <Route path="/login" element={<IfLoggedInRedirect><Login /></IfLoggedInRedirect>} />
            <Route path="/" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
            <Route path="/shipments/:id" element={<ProtectedLayout><ShipmentDetail /></ProtectedLayout>} />
            <Route path="/analytics" element={<ProtectedLayout><Analytics /></ProtectedLayout>} />
            <Route path="/settings" element={<ProtectedLayout><Settings /></ProtectedLayout>} />
            <Route
              path="/admin"
              element={(
                <ProtectedRoute>
                  <AdminRoute>
                    <Layout><Admin /></Layout>
                  </AdminRoute>
                </ProtectedRoute>
              )}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </AuthProvider>
    </ThemeProvider>
  )
}
