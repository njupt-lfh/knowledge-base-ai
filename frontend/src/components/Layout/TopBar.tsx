/**
 * 顶部品牌栏
 * 展示产品名、主题切换与版本号
 * 主要导出：默认 TopBar 组件
 */
import { Typography } from 'antd'
import { DatabaseOutlined } from '@ant-design/icons'
import ThemeToggle from '../common/ThemeToggle'
import './TopBar.css'

const { Text } = Typography

/** 固定顶栏，全宽品牌区 */
export default function TopBar() {
  return (
    <header className="topbar">
      <div className="topbar__brand">
        <DatabaseOutlined className="topbar__icon" />
        <div>
          <h1 className="topbar__title">KNOWLEDGE BASE AI</h1>
          <Text className="topbar__subtitle">智能知识库管理平台</Text>
        </div>
      </div>
      <div className="topbar__meta">
        <ThemeToggle />
        <span className="topbar__version">v1.0</span>
      </div>
    </header>
  )
}
