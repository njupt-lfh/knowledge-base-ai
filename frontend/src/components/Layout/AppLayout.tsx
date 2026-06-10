/**
 * 应用主布局（v2）
 * 顶部导航栏 + 内容区（无全局侧栏）
 */
import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import GridBackground from '../common/GridBackground'
import TopBar from './TopBar'
import './AppLayout.css'

/** 知识库详情/对话等子路由：全宽工作区，由 KBLayout 控制边距 */
function isKbWorkspacePath(pathname: string): boolean {
  return /^\/knowledge-bases\/[^/]+/.test(pathname)
}

function isStatsPath(pathname: string): boolean {
  return pathname === '/stats'
}

export default function AppLayout() {
  const location = useLocation()
  const kbWorkspace = isKbWorkspacePath(location.pathname)
  const statsPage = isStatsPath(location.pathname)

  return (
    <div className="app-layout">
      <GridBackground />
      <TopBar />
      <main className="app-layout__content">
        <div className="app-layout__page">
          {kbWorkspace ? (
            <div key={location.pathname} className="app-layout__viewport">
              <Outlet />
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                className={
                  statsPage ? 'app-layout__shell app-layout__shell--stats' : 'app-layout__shell'
                }
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </main>
    </div>
  )
}
