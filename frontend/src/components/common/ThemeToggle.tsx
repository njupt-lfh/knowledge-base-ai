import { MoonOutlined, SunOutlined } from '@ant-design/icons'
import { Tooltip } from 'antd'
import { useThemeStore } from '../../stores/themeStore'
import './ThemeToggle.css'

export default function ThemeToggle() {
  const { mode, toggle } = useThemeStore()
  const isDark = mode === 'dark'

  return (
    <Tooltip title={isDark ? '切换浅色主题' : '切换暗色主题'}>
      <button
        type="button"
        className="theme-toggle"
        onClick={toggle}
        aria-label={isDark ? '切换浅色主题' : '切换暗色主题'}
      >
        {isDark ? <SunOutlined /> : <MoonOutlined />}
        <span className="theme-toggle__label">{isDark ? '浅色' : '暗色'}</span>
      </button>
    </Tooltip>
  )
}
