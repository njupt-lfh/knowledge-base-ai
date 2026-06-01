/**
 * 应用入口文件
 * 负责：加载全局样式、在 React 挂载前从 localStorage 恢复主题、挂载根组件
 * 主要导出：无（副作用入口）
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/animations.css'
import './styles/hud-panel.css'
import './index.css'
import ThemeProvider from './components/common/ThemeProvider'
import App from './App.tsx'

// 首屏闪烁防护：在 React 渲染前同步 data-theme，避免暗/亮主题切换闪烁
try {
  const raw = localStorage.getItem('kb-theme-mode')
  if (raw) {
    const parsed = JSON.parse(raw) as { state?: { mode?: string } }
    const mode = parsed?.state?.mode
    if (mode === 'light' || mode === 'dark') {
      document.documentElement.setAttribute('data-theme', mode)
    }
  }
} catch {
  document.documentElement.setAttribute('data-theme', 'dark')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
)
