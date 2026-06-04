/**
 * 知识库子页布局（v2）
 * 左侧 KB 导航栏 + 右侧内容区
 */
import { useEffect, useState } from 'react'
import { Outlet, useParams, useLocation, useNavigate } from 'react-router-dom'
import { knowledgeApi } from '../../api/knowledge'
import KBSidebar from './KBSidebar'
import { kbSidebarItems } from './kbSidebarConfig'
import './KBLayout.css'

export default function KBLayout() {
  const { kbId } = useParams<{ kbId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [kbName, setKbName] = useState<string>()

  useEffect(() => {
    if (!kbId) {
      setKbName(undefined)
      return
    }
    let cancelled = false
    knowledgeApi
      .getById(kbId)
      .then((res) => {
        if (!cancelled) setKbName(res.data.name)
      })
      .catch(() => {
        if (!cancelled) setKbName(undefined)
      })
    return () => {
      cancelled = true
    }
  }, [kbId])

  const pathname = location.pathname
  const activeKey = pathname.endsWith('/chat')
    ? 'chat'
    : pathname.endsWith('/gaps')
      ? 'gaps'
      : new URLSearchParams(location.search).get('tab') || 'documents'

  const handleSelect = (key: string) => {
    if (key === 'chat') {
      navigate(`/knowledge-bases/${kbId}/chat`)
    } else if (key === 'gaps') {
      navigate(`/knowledge-bases/${kbId}/gaps`)
    } else {
      navigate(`/knowledge-bases/${kbId}?tab=${key}`)
    }
  }

  return (
    <div className="kb-layout">
      <KBSidebar
        items={kbSidebarItems}
        activeKey={activeKey}
        onSelect={handleSelect}
        kbName={kbName}
      />
      <div className="kb-layout__content">
        <Outlet />
      </div>
    </div>
  )
}
