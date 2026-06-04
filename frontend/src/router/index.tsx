/**
 * 前端路由配置（v2 布局）
 * TopBar 全局导航 + KB 内左侧栏
 */
import { createBrowserRouter, Navigate } from 'react-router-dom'
import AppLayout from '../components/Layout/AppLayout'
import KBLayout from '../components/Layout/KBLayout'
import KnowledgeList from '../pages/KnowledgeList'
import KnowledgeDetail from '../pages/KnowledgeDetail'
import ChatAgent from '../pages/ChatAgent'
import Stats from '../pages/Stats'
import ShareChat from '../pages/ShareChat'
import GapTasks from '../pages/GapTasks'
import EvalDashboard from '../pages/EvalDashboard'

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/knowledge-bases" replace /> },
      { path: 'knowledge-bases', element: <KnowledgeList /> },
      {
        path: 'knowledge-bases/:kbId',
        element: <KBLayout />,
        children: [
          { index: true, element: <KnowledgeDetail /> },
          { path: 'chat', element: <ChatAgent /> },
          { path: 'gaps', element: <GapTasks /> },
        ],
      },
      { path: 'stats', element: <Stats /> },
      { path: 'eval', element: <EvalDashboard /> },
    ],
  },
  { path: '/share/:token', element: <ShareChat /> },
])

export default router
