import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'dark' | 'light'

interface ThemeState {
  mode: ThemeMode
  toggle: () => void
  setMode: (mode: ThemeMode) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: 'dark',
      toggle: () => set({ mode: get().mode === 'dark' ? 'light' : 'dark' }),
      setMode: (mode) => set({ mode }),
    }),
    { name: 'kb-theme-mode' },
  ),
)
