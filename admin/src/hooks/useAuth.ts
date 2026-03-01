import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import type { AdminUser } from '@/types'

interface UseAuthReturn {
  user: AdminUser | null
  isAuthenticated: boolean
  isLoading: boolean
  logout: () => void
}

export function useAuth(): UseAuthReturn {
  const navigate = useNavigate()
  const { user, isAuthenticated, logout: storeLogout } = useAuthStore()

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login')
    }
  }, [isAuthenticated, navigate])

  const logout = () => {
    storeLogout()
    navigate('/login')
  }

  return {
    user,
    isAuthenticated,
    isLoading: false,
    logout,
  }
}
