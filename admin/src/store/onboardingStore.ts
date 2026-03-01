import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const TOTAL_STEPS = 6

interface OnboardingState {
  currentStep: number
  completedByUser: Record<string, boolean>

  setStep: (step: number) => void
  nextStep: () => void
  prevStep: () => void
  completeOnboarding: (userId: string) => void
  isCompleted: (userId: string) => boolean
  resetForUser: (userId: string) => void
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      currentStep: 0,
      completedByUser: {},

      setStep: (step: number) => set({ currentStep: step }),
      nextStep: () =>
        set((s) => ({
          currentStep: Math.min(s.currentStep + 1, TOTAL_STEPS - 1),
        })),
      prevStep: () =>
        set((s) => ({
          currentStep: Math.max(s.currentStep - 1, 0),
        })),
      completeOnboarding: (userId: string) =>
        set((s) => ({
          completedByUser: { ...s.completedByUser, [userId]: true },
          currentStep: 0,
        })),
      isCompleted: (userId: string) => !!get().completedByUser[userId],
      resetForUser: (userId: string) =>
        set((s) => ({
          completedByUser: { ...s.completedByUser, [userId]: false },
          currentStep: 0,
        })),
    }),
    {
      name: 'onboarding-storage',
      partialize: (state) => ({
        completedByUser: state.completedByUser,
        currentStep: state.currentStep,
      }),
    },
  ),
)
