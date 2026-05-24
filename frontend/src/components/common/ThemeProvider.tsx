import { useEffect, useMemo, type ReactNode } from 'react'
import { ConfigProvider, theme as antdTheme } from 'antd'
import { useThemeStore } from '../../stores/themeStore'
import { getAntdTheme } from '../../styles/theme'

export default function ThemeProvider({ children }: { children: ReactNode }) {
  const mode = useThemeStore((s) => s.mode)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', mode)
  }, [mode])

  const config = useMemo(
    () => ({
      ...getAntdTheme(mode),
      algorithm: mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    }),
    [mode],
  )

  return <ConfigProvider theme={config}>{children}</ConfigProvider>
}
