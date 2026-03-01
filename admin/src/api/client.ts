import axios, { type InternalAxiosRequestConfig } from 'axios'
import { message } from 'antd'
import { useImpersonationStore } from '@/store/impersonationStore'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach JWT + impersonation header
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Attach impersonation header when admin is viewing as a manager
    const { impersonatedManagerId } = useImpersonationStore.getState()
    if (impersonatedManagerId && config.headers) {
      config.headers['X-Impersonate-Manager-Id'] = impersonatedManagerId
    }

    return config
  },
  (error) => Promise.reject(error),
)

// Track whether we are currently refreshing to avoid infinite loops
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value: unknown) => void
  reject: (reason: unknown) => void
}> = []

const processQueue = (error: unknown) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(undefined)
    }
  })
  failedQueue = []
}

// Response interceptor: handle 401 (refresh), 403, 500
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(() => api(originalRequest))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        // No refresh token, redirect to login
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        const response = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refreshToken,
        })
        const { access_token, refresh_token: newRefreshToken } = response.data
        localStorage.setItem('access_token', access_token)
        localStorage.setItem('refresh_token', newRefreshToken)
        processQueue(null)
        return api(originalRequest)
      } catch {
        processQueue(error)
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
        return Promise.reject(error)
      } finally {
        isRefreshing = false
      }
    }

    if (error.response?.status === 403) {
      message.error('Нет доступа')
    }

    if (error.response?.status === 500) {
      message.error('Ошибка сервера')
    }

    return Promise.reject(error)
  },
)

export default api
