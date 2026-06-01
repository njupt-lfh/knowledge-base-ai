/**
 * 知识库卡片网格布局
 * 首格为新建卡片，其余为 KnowledgeCard
 * 主要导出：默认 KnowledgeCardGrid 组件
 */
import type { KnowledgeBase } from '../../types'
import KnowledgeCard from './KnowledgeCard'
import CreateCard from './CreateCard'
import './KnowledgeCard.css'

interface KnowledgeCardGridProps {
  data: KnowledgeBase[]
  loading?: boolean
  onCreate: () => void
  onView: (id: string) => void
  onChat: (id: string) => void
  onEdit: (kb: KnowledgeBase) => void
  onDelete: (id: string) => void
}

/** 知识库列表页卡片网格 */
export default function KnowledgeCardGrid({
  data,
  loading,
  onCreate,
  onView,
  onChat,
  onEdit,
  onDelete,
}: KnowledgeCardGridProps) {
  const maxHits = Math.max(...data.map((kb) => kb.total_hits ?? 0), 1)

  if (loading && data.length === 0) {
    return <div className="kb-list-empty">加载中...</div>
  }

  return (
    <div className="kb-grid">
      <CreateCard onClick={onCreate} index={0} />
      {data.map((kb, i) => (
        <KnowledgeCard
          key={kb.id}
          kb={kb}
          index={i + 1}
          maxHits={maxHits}
          onView={onView}
          onChat={onChat}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
      {!loading && data.length === 0 && (
        <div className="kb-list-empty">暂无知识库，点击左侧卡片创建</div>
      )}
    </div>
  )
}
