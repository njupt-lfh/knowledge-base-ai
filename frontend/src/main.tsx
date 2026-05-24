import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/tokens.css'
import './styles/animations.css'
import './styles/hud-panel.css'
import './index.css'
import ThemeProvider from './components/common/ThemeProvider'
import App from './App.tsx'

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
