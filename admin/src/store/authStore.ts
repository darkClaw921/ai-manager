import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authAPI } from '@/api'
import type { AdminUser } from '@/types'

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: AdminUser | null
  isAuthenticated: boolean

  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<void>
  setUser: (user: AdminUser) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      login: async (email: string, password: string) => {
        const response = await authAPI.login(email, password)
        const { access_token, refresh_token, user } = response.data

        localStorage.setItem('access_token', access_token)
        localStorage.setItem('refresh_token', refresh_token)

        set({
          token: access_token,
          refreshToken: refresh_token,
          user,
          isAuthenticated: true,
        })
      },

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')

        set({
          token: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        })
      },

      refreshAccessToken: async () => {
        const currentRefreshToken = get().refreshToken
        if (!currentRefreshToken) {
          get().logout()
          return
        }

        try {
          const response = await authAPI.refresh(currentRefreshToken)
          const { access_token, refresh_token, user } = response.data

          localStorage.setItem('access_token', access_token)
          localStorage.setItem('refresh_token', refresh_token)

          set({
            token: access_token,
            refreshToken: refresh_token,
            user,
            isAuthenticated: true,
          })
        } catch {
          get().logout()
        }
      },

      setUser: (user: AdminUser) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
)
