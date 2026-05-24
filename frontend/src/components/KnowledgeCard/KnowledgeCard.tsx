import { motion } from 'framer-motion'
import { Typography, Popconfirm, Tooltip } from 'antd'
import {
  FileTextOutlined,
  DeleteOutlined,
  EditOutlined,
  MessageOutlined,
  EyeOutlined,
  FireOutlined,
} from '@ant-design/icons'
import type { KnowledgeBase } from '../../types'
import CountUpNumber from '../common/CountUpNumber'
import './KnowledgeCard.css'

const { Text, Paragraph } = Typography

interface KnowledgeCardProps {
  kb: KnowledgeBase
  index: number
  maxHits: number
  onView: (id: string) => void
  onChat: (id: string) => void
  onEdit: (kb: KnowledgeBase) => void
  onDelete: (id: string) => void
}

export default function KnowledgeCard({
  kb,
  index,
  maxHits,
  onView,
  onChat,
  onEdit,
  onDelete,
}: KnowledgeCardProps) {
  const hits = kb.total_hits ?? 0
  const heatPercent = maxHits > 0 ? Math.max(4, (hits / maxHits) * 100) : 4
  const isHot = hits > 0 && hits >= maxHits * 0.5

  return (
    <motion.div
      className={`kb-card hud-panel ${isHot ? 'hud-panel--hot kb-card--hot' : ''}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
    >
      <span className="hud-corner-br" />

      <div className="kb-card__header">
        <h3 className="kb-card__title">{kb.name}</h3>
        {isHot && (
          <span className="hud-tag hud-tag--hot">
            <FireOutlined /> HOT
          </span>
        )}
      </div>

      <Paragraph className="kb-card__desc" ellipsis={{ rows: 2 }}>
        {kb.description || '暂无描述'}
      </Paragraph>

      <div className="kb-card__stats">
        <div className="kb-card__stat">
          <FileTextOutlined className="kb-card__stat-icon" />
          <div>
            <CountUpNumber end={kb.document_count} className="kb-card__stat-value" />
            <span className="hud-stat-label">文档</span>
          </div>
        </div>
        <div className="kb-card__stat">
          <FireOutlined className="kb-card__stat-icon kb-card__stat-icon--hot" />
          <div>
            <CountUpNumber end={hits} className="kb-card__stat-value kb-card__stat-value--hot" />
            <span className="hud-stat-label">命中</span>
          </div>
        </div>
      </div>

      <div className="heat-bar">
        <div className="heat-bar__fill" style={{ width: `${heatPercent}%` }} />
      </div>

      <div className="kb-card__meta">
        <Text type="secondary" className="kb-card__date">
          {new Date(kb.created_at).toLocaleDateString('zh-CN')}
        </Text>
        <span className="hud-tag">chunk {kb.chunk_size}</span>
      </div>

      <div className="kb-card__actions">
        <Tooltip title="查看详情">
          <button type="button" className="kb-card__btn" onClick={() => onView(kb.id)}>
            <EyeOutlined /> 查看
          </button>
        </Tooltip>
        <Tooltip title="智能对话">
          <button type="button" className="kb-card__btn kb-card__btn--primary" onClick={() => onChat(kb.id)}>
            <MessageOutlined /> 对话
          </button>
        </Tooltip>
        <Tooltip title="编辑">
          <button type="button" className="kb-card__btn kb-card__btn--icon" onClick={() => onEdit(kb)}>
            <EditOutlined />
          </button>
        </Tooltip>
        <Popconfirm title="确定删除此知识库?" onConfirm={() => onDelete(kb.id)}>
          <Tooltip title="删除">
            <button type="button" className="kb-card__btn kb-card__btn--icon kb-card__btn--danger">
              <DeleteOutlined />
            </button>
          </Tooltip>
        </Popconfirm>
      </div>
    </motion.div>
  )
}
