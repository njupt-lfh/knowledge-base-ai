import { AlertOutlined } from '@ant-design/icons'
import type { ColdKnowledgeStats } from '../../api/stats'
import './ColdKnowledgeBadge.css'

interface ColdKnowledgeBadgeProps {
  data: ColdKnowledgeStats | null | undefined
  compact?: boolean
}

export default function ColdKnowledgeBadge({ data, compact = false }: ColdKnowledgeBadgeProps) {
  if (!data) return null

  const count = data.cold_count_90d

  if (compact) {
    return (
      <span className={`cold-badge cold-badge--inline ${count > 0 ? 'cold-badge--warn' : 'cold-badge--ok'}`}>
        <AlertOutlined className="cold-badge__icon" />
        <span className="cold-badge__text">
          <span className="cold-badge__count">{count}</span>
          <span className="cold-badge__label">冷知识 (≥{data.threshold_days}天 0命中)</span>
        </span>
      </span>
    )
  }

  return (
    <div className={`cold-badge ${count > 0 ? 'cold-badge--warn' : 'cold-badge--ok'}`}>
      <AlertOutlined className="cold-badge__icon" />
      <div className="cold-badge__text">
        <span className="cold-badge__count">{count}</span>
        <span className="cold-badge__label">
          冷知识预警：{count} 个知识块在 {data.threshold_days} 天内零命中，建议治理
        </span>
        {data.cold_count_total > count && (
          <span className="cold-badge__sub">
            另有 {data.cold_count_total - count} 个较新知识块尚未被命中
          </span>
        )}
      </div>
    </div>
  )
}
