/**
 * 知识库治理建议面板
 * 扫描冷知识/重复/低质量 chunk 并执行归档、禁用等动作
 * 主要导出：默认 GovernancePanel 组件
 */
import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import { ReloadOutlined, ToolOutlined } from '@ant-design/icons'
import ColdKnowledgeBadge from '../Charts/ColdKnowledgeBadge'
import {
  governanceApi,
  type GovernanceScanResult,
  type GovernanceSuggestion,
} from '../../api/governance'
import type { ColdKnowledgeStats } from '../../api/stats'
import './GovernancePanel.css'

const TYPE_LABELS: Record<string, string> = {
  duplicate: '重复',
  cold_stale: '冷知识',
  high_quality_zero_hit: '高质量零命中',
  low_quality: '低质量',
  archive_candidate: '建议归档',
}

const SEVERITY_LABELS: Record<string, string> = {
  error: '高',
  warning: '中',
  info: '低',
}

const ACTION_LABELS: Record<string, string> = {
  archive: '归档',
  deactivate: '禁用',
  boost_faq: '提升权重',
  merge: '合并提示',
}

const SEVERITY_COLOR: Record<string, string> = {
  info: 'blue',
  warning: 'orange',
  error: 'red',
}

interface GovernancePanelProps {
  kbId: string
  onApplied?: () => void
}

/**
 * 知识库详情「治理建议」Tab 内容
 * @param onApplied 治理动作成功后通知父组件刷新健康度/冷知识统计
 */
export default function GovernancePanel({ kbId, onApplied }: GovernancePanelProps) {
  const [data, setData] = useState<GovernanceScanResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [actingId, setActingId] = useState<string | null>(null)

  const fetchScan = useCallback(async () => {
    setLoading(true)
    try {
      // scanDuplicates=false 加快扫描，重复项由专门流程处理
      const res = await governanceApi.scan(kbId, false)
      setData(res.data)
    } catch {
      message.error('获取治理建议失败')
    }
    setLoading(false)
  }, [kbId])

  useEffect(() => {
    fetchScan()
  }, [fetchScan])

  const handleApply = async (row: GovernanceSuggestion, action?: string) => {
    const act = action || row.recommended_action
    if (act === 'merge') {
      message.info('请在文档分块列表中编辑后禁用重复项')
      return
    }
    setActingId(row.id)
    try {
      const res = await governanceApi.apply(kbId, act, row.chunk_ids)
      message.success(`已处理 ${res.data.applied} 项`)
      onApplied?.()
      fetchScan()
    } catch {
      message.error('执行治理动作失败')
    }
    setActingId(null)
  }

  const health = data?.health
  const coldBadge: ColdKnowledgeStats | null = health
    ? {
        cold_count_90d: health.cold_count_90d,
        cold_count_total: health.cold_count_total,
        threshold_days: health.threshold_days,
      }
    : null

  const columns = [
    {
      title: '类型',
      dataIndex: 'type',
      width: 120,
      render: (t: string) => <Tag>{TYPE_LABELS[t] || t}</Tag>,
    },
    {
      title: '建议',
      key: 'title',
      render: (_: unknown, row: GovernanceSuggestion) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{row.title}</Typography.Text>
          <Typography.Text type="secondary">{row.description}</Typography.Text>
          <Typography.Text type="secondary" className="gov-preview">
            {row.content_preview}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'severity',
      width: 90,
      render: (s: string) => (
        <Tag color={SEVERITY_COLOR[s] || 'default'}>{SEVERITY_LABELS[s] || s}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, row: GovernanceSuggestion) => {
        const actions = [row.recommended_action]
        // 低质量、冷知识类型提供归档/禁用的交叉选项
        if (row.type === 'low_quality') {
          if (!actions.includes('archive')) actions.push('archive')
        }
        if (row.type === 'cold_stale') {
          if (!actions.includes('deactivate')) actions.push('deactivate')
        }
        return (
          <Space size="small">
            {actions.map((action) => {
              const btn = (
                <Button
                  key={action}
                  size="small"
                  type={action === row.recommended_action ? 'primary' : 'default'}
                  loading={actingId === row.id}
                >
                  {ACTION_LABELS[action] || action}
                </Button>
              )
              if (action === 'deactivate' || action === 'archive') {
                return (
                  <Popconfirm
                    key={action}
                    title={`确定${ACTION_LABELS[action]}？`}
                    onConfirm={() => handleApply(row, action)}
                  >
                    {btn}
                  </Popconfirm>
                )
              }
              return (
                <span key={action} onClick={() => handleApply(row, action)}>
                  {btn}
                </span>
              )
            })}
          </Space>
        )
      },
    },
  ]

  return (
    <Space
      direction="vertical"
      style={{ width: '100%' }}
      size="middle"
      className="governance-panel"
    >
      <Space wrap align="center" className="governance-panel__toolbar">
        <ColdKnowledgeBadge data={coldBadge} />
        {health && (
          <Card size="small" className="governance-panel__stat">
            <Typography.Text type="secondary">活跃块 </Typography.Text>
            <Typography.Text strong>{health.active_chunks}</Typography.Text>
            <Typography.Text type="secondary"> / {health.total_chunks}</Typography.Text>
          </Card>
        )}
        {health && (
          <Card size="small" className="governance-panel__stat">
            <Typography.Text type="secondary">待处理建议 </Typography.Text>
            <Typography.Text strong>{health.suggestions_count}</Typography.Text>
          </Card>
        )}
        <Button icon={<ReloadOutlined />} onClick={fetchScan} loading={loading}>
          重新扫描
        </Button>
      </Space>

      {data?.suggestions.length === 0 && !loading && (
        <Typography.Text type="secondary">
          <ToolOutlined /> 暂无治理建议，知识库状态良好
        </Typography.Text>
      )}

      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data?.suggestions || []}
        pagination={{ pageSize: 10 }}
        size="small"
      />
    </Space>
  )
}
