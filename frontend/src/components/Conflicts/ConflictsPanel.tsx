/**
 * 入库冲突裁决面板
 * 展示待处理相似度冲突、裁决历史，并支持保留新/旧内容或忽略
 * 主要导出：默认 ConflictsPanel 组件
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button, Popconfirm, Select, Space, Table, Tabs, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { HistoryOutlined, ReloadOutlined, WarningOutlined } from '@ant-design/icons'
import type { GovernanceChunkRef } from '../../api/governance'
import { conflictsApi, type ConflictListStatus, type KnowledgeConflict } from '../../api/conflicts'
import './ConflictsPanel.css'

interface ConflictsPanelProps {
  kbId: string
  /** 在文档知识块抽屉中定位到指定块；chunkId 省略时仅打开来源文档 */
  onLocateChunk?: (documentId: string, chunkId?: string) => void
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待裁决',
  resolved_keep_new: '保留新内容',
  resolved_keep_old: '保留已有',
  dismissed: '已忽略',
}

function formatChunkLabel(ref: GovernanceChunkRef): string {
  return `${ref.document_name} · 第 ${ref.chunk_index} 段`
}

function ConflictChunkSource({
  label,
  preview,
  refInfo,
  documentName,
  onLocate,
  locateLabel = '查看知识块',
}: {
  label: string
  preview: string
  refInfo?: GovernanceChunkRef | null
  documentName?: string | null
  onLocate?: () => void
  locateLabel?: string
}) {
  const sourceLabel = refInfo
    ? formatChunkLabel(refInfo)
    : documentName
      ? `《${documentName}》`
      : null

  return (
    <div className="conflicts-panel__source">
      <Space size={4} wrap>
        <Typography.Text type="secondary">{label}</Typography.Text>
        {sourceLabel && (
          <Typography.Text type="secondary" className="conflicts-panel__source-label">
            {sourceLabel}
            {refInfo && !refInfo.is_active && (
              <Tag color="default" style={{ marginLeft: 6 }}>
                已禁用
              </Tag>
            )}
          </Typography.Text>
        )}
        {onLocate && (
          <Button type="link" size="small" className="conflicts-panel__locate" onClick={onLocate}>
            {locateLabel}
          </Button>
        )}
      </Space>
      <Typography.Paragraph
        type="secondary"
        ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
        className="conflicts-panel__preview"
      >
        {preview}
      </Typography.Paragraph>
    </div>
  )
}

function renderConflictCompare(
  row: KnowledgeConflict,
  onLocateChunk?: (documentId: string, chunkId?: string) => void,
) {
  return (
    <Space direction="vertical" size={8} className="conflicts-panel__compare">
      <ConflictChunkSource
        label="已有："
        preview={row.existing_preview}
        refInfo={row.existing_chunk_ref}
        onLocate={
          row.existing_chunk_ref && onLocateChunk
            ? () =>
                onLocateChunk(row.existing_chunk_ref!.document_id, row.existing_chunk_ref!.chunk_id)
            : undefined
        }
      />
      <ConflictChunkSource
        label="待入库："
        preview={row.new_preview}
        documentName={row.source_document_name}
        onLocate={
          row.source_document_id && onLocateChunk
            ? () => onLocateChunk(row.source_document_id!)
            : undefined
        }
        locateLabel="查看来源文档"
      />
      {row.resolved_chunk_ref && onLocateChunk && (
        <ConflictChunkSource
          label="裁决结果："
          preview={row.resolved_chunk_ref.preview ?? row.new_preview}
          refInfo={row.resolved_chunk_ref}
          onLocate={() =>
            onLocateChunk(row.resolved_chunk_ref!.document_id, row.resolved_chunk_ref!.chunk_id)
          }
        />
      )}
      {row.llm_reason && (
        <Typography.Text type="danger" className="conflicts-panel__reason">
          {row.llm_reason}
        </Typography.Text>
      )}
    </Space>
  )
}

/** 知识库详情「入库冲突」Tab：LLM 矛盾检测队列与裁决历史 */
export default function ConflictsPanel({ kbId, onLocateChunk }: ConflictsPanelProps) {
  const [activeTab, setActiveTab] = useState<'pending' | 'history'>('pending')
  const [pendingRows, setPendingRows] = useState<KnowledgeConflict[]>([])
  const [historyRows, setHistoryRows] = useState<KnowledgeConflict[]>([])
  const [loading, setLoading] = useState(false)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [rollingBackId, setRollingBackId] = useState<string | null>(null)
  const [historyFilter, setHistoryFilter] = useState<ConflictListStatus | undefined>(undefined)

  const fetchPending = useCallback(async () => {
    setLoading(true)
    try {
      const res = await conflictsApi.list(kbId, 'pending')
      setPendingRows(res.data)
    } catch {
      message.error('获取待裁决冲突失败')
    }
    setLoading(false)
  }, [kbId])

  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try {
      const res = await conflictsApi.list(kbId, historyFilter ?? 'history', 100)
      setHistoryRows(res.data)
    } catch {
      message.error('获取裁决历史失败')
    }
    setLoading(false)
  }, [kbId, historyFilter])

  useEffect(() => {
    if (activeTab === 'pending') {
      void fetchPending()
    } else {
      void fetchHistory()
    }
  }, [activeTab, fetchPending, fetchHistory])

  const refreshAll = useCallback(async () => {
    await Promise.all([fetchPending(), fetchHistory()])
  }, [fetchPending, fetchHistory])

  const resolve = async (id: string, resolution: string) => {
    setResolvingId(id)
    try {
      await conflictsApi.resolve(kbId, id, resolution)
      message.success('已裁决')
      await refreshAll()
    } catch {
      message.error('裁决失败')
    }
    setResolvingId(null)
  }

  const rollback = async (id: string) => {
    setRollingBackId(id)
    try {
      const res = await conflictsApi.rollback(kbId, id)
      const prev = res.data.prev_status
        ? STATUS_LABELS[res.data.prev_status] || res.data.prev_status
        : ''
      message.success(prev ? `已回退（${prev} → 待裁决）` : '已回退到待裁决')
      await refreshAll()
      setActiveTab('pending')
    } catch {
      message.error('回退失败')
    }
    setRollingBackId(null)
  }

  const pendingColumns: ColumnsType<KnowledgeConflict> = useMemo(
    () => [
      {
        title: '相似度',
        dataIndex: 'similarity',
        width: 90,
        render: (v: number) => <Tag color="orange">{v}</Tag>,
      },
      {
        title: '已有 / 待入库',
        key: 'content',
        render: (_: unknown, row) => renderConflictCompare(row, onLocateChunk),
      },
      {
        title: '操作',
        key: 'actions',
        width: 280,
        render: (_: unknown, row) => (
          <Space wrap>
            <Button
              size="small"
              type="primary"
              loading={resolvingId === row.id}
              onClick={() => resolve(row.id, 'resolved_keep_new')}
            >
              保留新内容
            </Button>
            <Button size="small" onClick={() => resolve(row.id, 'resolved_keep_old')}>
              保留已有
            </Button>
            <Popconfirm title="确定忽略此冲突？" onConfirm={() => resolve(row.id, 'dismissed')}>
              <Button size="small" danger>
                忽略
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [onLocateChunk, resolvingId],
  )

  const historyColumns: ColumnsType<KnowledgeConflict> = useMemo(
    () => [
      {
        title: '裁决时间',
        dataIndex: 'resolved_at',
        width: 160,
        render: (t: string | null) => (t ? new Date(t).toLocaleString() : '—'),
      },
      {
        title: '裁决结果',
        dataIndex: 'status',
        width: 110,
        render: (s: string) => (
          <Tag color={s === 'dismissed' ? 'default' : 'green'}>{STATUS_LABELS[s] || s}</Tag>
        ),
      },
      {
        title: '相似度',
        dataIndex: 'similarity',
        width: 90,
        render: (v: number) => <Tag color="orange">{v}</Tag>,
      },
      {
        title: '冲突内容',
        key: 'content',
        render: (_: unknown, row) => renderConflictCompare(row, onLocateChunk),
      },
      {
        title: '发现时间',
        dataIndex: 'created_at',
        width: 160,
        render: (t: string | null) => (t ? new Date(t).toLocaleString() : '—'),
      },
      {
        title: '操作',
        key: 'actions',
        width: 100,
        render: (_: unknown, row) => (
          <Popconfirm
            title="确定回退到待裁决？"
            description={
              row.status === 'resolved_keep_new'
                ? '将删除误入库的新知识块，冲突重新进入待裁决队列。'
                : '冲突将重新进入待裁决队列。'
            }
            onConfirm={() => rollback(row.id)}
          >
            <Button size="small" danger loading={rollingBackId === row.id}>
              回退
            </Button>
          </Popconfirm>
        ),
      },
    ],
    [onLocateChunk, rollingBackId],
  )

  const tabItems = [
    {
      key: 'pending',
      label: `待裁决 (${pendingRows.length})`,
      children: (
        <>
          {pendingRows.length === 0 && !loading && (
            <Typography.Text type="secondary">暂无待裁决冲突</Typography.Text>
          )}
          <Table
            rowKey="id"
            size="small"
            loading={loading}
            columns={pendingColumns}
            dataSource={pendingRows}
            pagination={{ pageSize: 8 }}
          />
        </>
      ),
    },
    {
      key: 'history',
      label: (
        <Space size={4}>
          <HistoryOutlined />
          裁决历史 ({historyRows.length})
        </Space>
      ),
      children: (
        <>
          <Space className="conflicts-panel__history-filter" wrap>
            <Typography.Text type="secondary">筛选结果：</Typography.Text>
            <Select
              allowClear
              placeholder="全部已裁决"
              style={{ width: 140 }}
              value={historyFilter}
              onChange={(v) => setHistoryFilter(v)}
              options={(
                ['resolved_keep_new', 'resolved_keep_old', 'dismissed'] as ConflictListStatus[]
              ).map((k) => ({ value: k, label: STATUS_LABELS[k] }))}
            />
          </Space>
          {historyRows.length === 0 && !loading && (
            <Typography.Text type="secondary">暂无裁决历史</Typography.Text>
          )}
          <Table
            rowKey="id"
            size="small"
            loading={loading}
            columns={historyColumns}
            dataSource={historyRows}
            pagination={{ pageSize: 10 }}
          />
        </>
      ),
    },
  ]

  return (
    <div className="conflicts-panel">
      <Space wrap className="conflicts-panel__head">
        <Typography.Text type="secondary">
          <WarningOutlined /> 0.75–0.92 相似度区间经 LLM 矛盾检测（最多 3 次/块）
        </Typography.Text>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => (activeTab === 'pending' ? fetchPending() : fetchHistory())}
          loading={loading}
        >
          刷新
        </Button>
      </Space>
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'pending' | 'history')}
        items={tabItems}
        className="conflicts-panel__tabs"
      />
    </div>
  )
}
