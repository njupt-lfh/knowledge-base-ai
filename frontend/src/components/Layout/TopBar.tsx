/**
 * 顶部导航栏（sticky）
 * 全局入口（知识库/驾驶舱/评测）+ 主题切换 + 版本号
 */
import { useNavigate, useLocation } from 'react-router-dom'
import { Typography } from 'antd'
import { DatabaseOutlined, DashboardOutlined, ExperimentOutlined } from '@ant-design/icons'
import ThemeToggle from '../common/ThemeToggle'
import './TopBar.css'

const { Text } = Typography

const navItems = [
  { key: '/knowledge-bases', icon: DatabaseOutlined, label: '知识库管理' },
  { key: '/stats', icon: DashboardOutlined, label: '数据驾驶舱' },
  { key: '/eval', icon: ExperimentOutlined, label: '评测基线' },
]

export default function TopBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const activeKey = '/' + location.pathname.split('/')[1]

  return (
    <header className="topbar">
      <div className="topbar__brand">
        <DatabaseOutlined className="topbar__icon" />
        <span className="topbar__title">KNOWLEDGE BASE AI</span>
        <Text className="topbar__subtitle">智能知识库管理平台</Text>
      </div>
      <nav className="topbar__nav">
        {navItems.map(({ key, icon: Icon, label }) => (
          <button
            key={key}
            type="button"
            className={`topbar__nav-item ${activeKey === key ? 'topbar__nav-item--active' : ''}`}
            onClick={() => navigate(key)}
          >
            <Icon />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="topbar__meta">
        <ThemeToggle />
        <span className="topbar__version">v1.0</span>
      </div>
    </header>
  )
}
