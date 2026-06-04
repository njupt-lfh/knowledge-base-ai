/**
 * 知识库子页布局（v2）
 * 左侧 KB 导航栏 + 右侧内容区
 */
import { useEffect, useState } from 'react'
import { Outlet, useParams, useLocation, useNavigate } from 'react-router-dom'
import { knowledgeApi } from '../../api/knowledge'
import KBSidebar, { kbSidebarItems } from './KBSidebar'
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

  // 从 pathname 推断当前选中的 sidebar key
  const pathname = location.pathname
  let activeKey = 'documents'
  if (pathname.endsWith('/chat')) activeKey = 'chat'
  else if (pathname.endsWith('/gaps')) activeKey = 'gaps'
  else {
    // KB detail 页面可能有 query param 指定 tab
    const params = new URLSearchParams(location.search)
    activeKey = params.get('tab') || 'documents'
  }

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
