/**
 * Ant Design 主题提供者
 * 同步 Zustand 主题到 data-theme 与 ConfigProvider
 * 主要导出：默认 ThemeProvider 组件
 */
import { useEffect, useMemo, type ReactNode } from 'react'
import { ConfigProvider, theme as antdTheme } from 'antd'
import { useThemeStore } from '../../stores/themeStore'
import { getAntdTheme } from '../../styles/theme'

/**
 * 包裹应用根节点，注入 Ant Design 主题算法
 * @param children 子组件树
 */
export default function ThemeProvider({ children }: { children: ReactNode }) {
  const mode = useThemeStore((s) => s.mode)

  // 与 CSS 变量 tokens.css 联动
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
