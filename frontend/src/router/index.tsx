import { createBrowserRouter, Navigate } from 'react-router-dom'
import AppLayout from '../components/Layout/AppLayout'
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
      { path: 'knowledge-bases/:kbId', element: <KnowledgeDetail /> },
      { path: 'knowledge-bases/:kbId/chat', element: <ChatAgent /> },
      { path: 'knowledge-bases/:kbId/gaps', element: <GapTasks /> },
      { path: 'stats', element: <Stats /> },
      { path: 'eval', element: <EvalDashboard /> },
    ],
  },
  { path: '/share/:token', element: <ShareChat /> },
])

export default router
