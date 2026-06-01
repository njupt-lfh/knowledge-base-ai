/**
 * 主题状态管理（Zustand + localStorage 持久化）
 * 主要导出：ThemeMode 类型、useThemeStore
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/** 支持的主题模式 */
export type ThemeMode = 'dark' | 'light'

interface ThemeState {
  mode: ThemeMode
  toggle: () => void
  setMode: (mode: ThemeMode) => void
}

/** 全局主题 store，键名 kb-theme-mode 与 main.tsx 首屏恢复逻辑一致 */
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
