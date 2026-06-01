/**
 * 左侧主导航
 * 知识库、数据驾驶舱、评测基线三个一级入口
 * 主要导出：默认 SideNav 组件
 */
import { useNavigate, useLocation } from 'react-router-dom'
import { DatabaseOutlined, DashboardOutlined, ExperimentOutlined } from '@ant-design/icons'
import './SideNav.css'

const menuItems = [
  { key: '/knowledge-bases', icon: DatabaseOutlined, label: '知识库管理' },
  { key: '/stats', icon: DashboardOutlined, label: '数据驾驶舱' },
  { key: '/eval', icon: ExperimentOutlined, label: '评测基线' },
]

interface SideNavProps {
  collapsed: boolean
}

/**
 * 可折叠侧栏导航
 * @param collapsed 是否仅显示图标
 */
export default function SideNav({ collapsed }: SideNavProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const selectedKey = '/' + location.pathname.split('/')[1]

  return (
    <nav className={`sidenav ${collapsed ? 'sidenav--collapsed' : ''}`}>
      <ul className="sidenav__list">
        {menuItems.map(({ key, icon: Icon, label }) => (
          <li key={key}>
            <button
              type="button"
              className={`sidenav__item ${selectedKey === key ? 'sidenav__item--active' : ''}`}
              onClick={() => navigate(key)}
              title={label}
            >
              <Icon className="sidenav__icon" />
              {!collapsed && <span className="sidenav__label">{label}</span>}
              {selectedKey === key && <span className="sidenav__indicator" />}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}
