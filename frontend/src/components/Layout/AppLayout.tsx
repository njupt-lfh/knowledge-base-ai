/**
 * 应用主布局
 * 顶栏 + 侧栏 + 带路由过渡动画的内容区
 * 主要导出：默认 AppLayout 组件
 */
import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import GridBackground from '../common/GridBackground'
import TopBar from './TopBar'
import SideNav from './SideNav'
import StatusIndicator from './StatusIndicator'
import './AppLayout.css'

/** 主应用壳层，子路由通过 Outlet 渲染 */
export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <div className="app-layout">
      <GridBackground />
      <TopBar />
      <div className="app-layout__body">
        <SideNav collapsed={collapsed} />
        <main className="app-layout__content">
          <div className="app-layout__content-header">
            <button
              type="button"
              className="app-layout__collapse-btn"
              onClick={() => setCollapsed(!collapsed)}
              aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
            >
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </button>
            <StatusIndicator />
          </div>
          <div className="app-layout__page">
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  )
}
