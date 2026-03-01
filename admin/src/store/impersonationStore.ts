import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface ImpersonationState {
  impersonatedManagerId: string | null
  impersonatedManagerName: string | null
  isImpersonating: boolean
  startImpersonation: (id: string, name: string) => void
  stopImpersonation: () => void
}

export const useImpersonationStore = create<ImpersonationState>()(
  persist(
    (set) => ({
      impersonatedManagerId: null,
      impersonatedManagerName: null,
      isImpersonating: false,

      startImpersonation: (id: string, name: string) =>
        set({
          impersonatedManagerId: id,
          impersonatedManagerName: name,
          isImpersonating: true,
        }),

      stopImpersonation: () =>
        set({
          impersonatedManagerId: null,
          impersonatedManagerName: null,
          isImpersonating: false,
        }),
    }),
    {
      name: 'impersonation-storage',
      storage: createJSONStorage(() => sessionStorage),
    },
  ),
)
