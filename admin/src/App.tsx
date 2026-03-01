import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, App as AntApp, theme, Spin } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ruRU from 'antd/locale/ru_RU'

import ProtectedRoute from '@/components/ProtectedRoute'
import { useThemeStore } from '@/store/themeStore'
import { useAuthStore } from '@/store/authStore'
import MainLayout from '@/components/MainLayout'
import LoginPage from '@/pages/LoginPage'

const LandingPage = lazy(() => import('@/pages/LandingPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const ManagersPage = lazy(() => import('@/pages/ManagersPage'))

const SuspenseFallback = <Spin size="large" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }} />

/** Shows landing for guests, redirects to /dashboard for authenticated users */
function LandingOrDashboard() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return <Suspense fallback={SuspenseFallback}><LandingPage /></Suspense>
}
import DashboardPage from '@/pages/DashboardPage'
import LeadsPage from '@/pages/LeadsPage'
import ConversationsPage from '@/pages/ConversationsPage'
import ConversationDetailPage from '@/pages/ConversationDetailPage'
import ScriptsPage from '@/pages/ScriptsPage'
import ChannelsPage from '@/pages/ChannelsPage'
import BookingsPage from '@/pages/BookingsPage'
import SettingsPage from '@/pages/SettingsPage'
import UsersPage from '@/pages/UsersPage'
import OnboardingPage from '@/pages/OnboardingPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  const isDark = useThemeStore((s) => s.isDark)

  return (
    <ConfigProvider
      locale={ruRU}
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <AntApp>
          <BrowserRouter>
            <Routes>
              {/* Public routes */}
              <Route path="/" element={<LandingOrDashboard />} />
              <Route path="/landing" element={<Navigate to="/" replace />} />
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/register"
                element={
                  <Suspense fallback={SuspenseFallback}>
                    <RegisterPage />
                  </Suspense>
                }
              />
              {/* Protected app routes */}
              <Route
                element={
                  <ProtectedRoute>
                    <MainLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="onboarding" element={<OnboardingPage />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="leads" element={<LeadsPage />} />
                <Route path="conversations" element={<ConversationsPage />} />
                <Route path="conversations/:id" element={<ConversationDetailPage />} />
                <Route path="scripts" element={<ScriptsPage />} />
                <Route path="channels" element={<ChannelsPage />} />
                <Route path="bookings" element={<BookingsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="users" element={<UsersPage />} />
                <Route
                  path="managers"
                  element={
                    <Suspense fallback={SuspenseFallback}>
                      <ManagersPage />
                    </Suspense>
                  }
                />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AntApp>
      </QueryClientProvider>
    </ConfigProvider>
  )
}

export default App
