/**
 * 知识库健康度摘要条
 * 展示等级、冷知识、缺口、冲突等快捷入口
 * 主要导出：默认 KnowledgeHealthPanel 组件
 */
import { useCallback, useEffect, useState } from 'react'
import { Card, Space, Tag, Typography } from 'antd'
import {
  AlertOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { healthApi, type KnowledgeBaseHealth } from '../../api/health'
import './KnowledgeHealthPanel.css'

const LEVEL_CONFIG = {
  healthy: { color: 'success', icon: <CheckCircleOutlined />, label: '健康' },
  attention: { color: 'warning', icon: <WarningOutlined />, label: '需关注' },
  critical: { color: 'error', icon: <ExclamationCircleOutlined />, label: '待治理' },
} as const

interface KnowledgeHealthPanelProps {
  kbId: string
  refreshToken?: number
  onNavigate?: (tab: 'governance' | 'conflicts' | 'gaps') => void
}

/**
 * 知识库详情页顶部健康条
 * @param refreshToken 父组件递增以触发重新拉取
 * @param onNavigate 点击指标跳转到对应 Tab 或缺口页
 */
export default function KnowledgeHealthPanel({
  kbId,
  refreshToken = 0,
  onNavigate,
}: KnowledgeHealthPanelProps) {
  const [health, setHealth] = useState<KnowledgeBaseHealth | null>(null)

  const fetchHealth = useCallback(async () => {
    try {
      setHealth((await healthApi.getKbHealth(kbId)).data)
    } catch {
      setHealth(null)
    }
  }, [kbId])

  useEffect(() => {
    fetchHealth()
  }, [fetchHealth, refreshToken])

  if (!health) return null

  const cfg = LEVEL_CONFIG[health.level] || LEVEL_CONFIG.attention

  return (
    <Card size="small" className="kb-health-panel">
      <Space wrap align="center" className="kb-health-panel__row">
        <Tag icon={cfg.icon} color={cfg.color} className="kb-health-panel__level">
          {cfg.label}
        </Tag>
        <Typography.Text type="secondary" className="kb-health-panel__metric">
          <AlertOutlined /> 冷知识 {health.cold.cold_count_90d}
        </Typography.Text>
        <button
          type="button"
          className="kb-health-panel__link"
          onClick={() => onNavigate?.('gaps')}
        >
          待补全 {health.pending_gaps}
        </button>
        <button
          type="button"
          className="kb-health-panel__link"
          onClick={() => onNavigate?.('conflicts')}
        >
          入库冲突 {health.pending_conflicts}
        </button>
        <button
          type="button"
          className="kb-health-panel__link"
          onClick={() => onNavigate?.('governance')}
        >
          低质量 {health.low_quality_chunks}
        </button>
        <Typography.Text type="secondary" className="kb-health-panel__metric">
          活跃块 {health.active_chunks}/{health.total_chunks}
        </Typography.Text>
      </Space>
    </Card>
  )
}
