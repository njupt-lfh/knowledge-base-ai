/**
 * 知识缺口补全任务页
 * 管理 RETRIEVAL_MISS / USER_CORRECTION 等待入库队列
 * 主要导出：默认 GapTasks 页面组件
 */
import { useCallback, useEffect, useState, type Key } from 'react'

import { useNavigate, useParams } from 'react-router-dom'
import {
  Button,
  Input,
  Modal,
  Popconfirm,
  message,
  Select,
  Space,
  Table,
  Tag,
  Tabs,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ArrowLeftOutlined, DeleteOutlined } from '@ant-design/icons'
import { gapApi, type GapAuditLogEntry, type KnowledgeGap } from '../api/gap'
import HudPanel from '../components/common/HudPanel'
import { formatDateTime } from '../utils/format'

const GAP_TYPE_LABEL: Record<string, string> = {
  RETRIEVAL_MISS: '检索未命中',
  USER_PROVIDED: '用户提供',
  USER_CORRECTION: '用户纠正',
  KNOWLEDGE_ABSENT: '知识缺失',
}

const PENDING_QUEUE_STATUSES = new Set(['pending', 'suggested', 'processing', 'manual_required'])
const COMPLETED_QUEUE_STATUSES = new Set(['approved', 'rejected'])

const STATUS_LABEL: Record<string, string> = {
  pending: '待处理',
  suggested: '待审批',
  processing: '入库中...',
  approved: '已入库',
  rejected: '已拒绝',
  manual_required: '待人工添加',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'gold',
  suggested: 'blue',
  processing: 'processing',
  approved: 'green',
  rejected: 'red',
  manual_required: 'orange',
}

const AUDIT_ACTION_LABEL: Record<string, string> = {
  created: '创建',
  status_changed: '状态变更',
  ingest_started: '开始入库',
  ingest_completed: '入库完成',
  ingest_failed: '入库失败',
  deleted: '删除',
  follow_up_created: '创建续补',
}

/** 解析 suggested_content JSON 或纯文本 */
function parseSuggested(raw: string | null): { title?: string; content?: string } | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as { title?: string; content?: string }
  } catch {
    return { content: raw }
  }
}

/** 单知识库 Gap Queue 工作台 */
export default function GapTasks() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [gaps, setGaps] = useState<KnowledgeGap[]>([])
  const [loading, setLoading] = useState(false)
  const [activeQueue, setActiveQueue] = useState<'pending' | 'completed'>('pending')
  const [activeType, setActiveType] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [manualModal, setManualModal] = useState<KnowledgeGap | null>(null)
  const [manualContent, setManualContent] = useState('')
  const [ingestingId, setIngestingId] = useState<string | null>(null)
  const [auditCache, setAuditCache] = useState<Record<string, GapAuditLogEntry[]>>({})
  const [auditLoadingId, setAuditLoadingId] = useState<string | null>(null)
  const [followUpModal, setFollowUpModal] = useState<KnowledgeGap | null>(null)
  const [followUpText, setFollowUpText] = useState('')
  const [followUpLoading, setFollowUpLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<Key[]>([])
  const [batchDeleting, setBatchDeleting] = useState(false)

  const singleDeleteTitle =
    activeQueue === 'completed'
      ? '确定删除此补全任务？不会删除已入库的文档内容。'
      : '确定删除此补全任务？'

  const fetchGaps = useCallback(async () => {
    if (!kbId) return
    setLoading(true)
    try {
      const params: { gap_type?: string; status?: string; queue: 'pending' | 'completed' } = {
        queue: activeQueue,
      }
      if (activeType !== 'all') params.gap_type = activeType
      if (statusFilter) params.status = statusFilter
      const res = await gapApi.list(kbId, params)
      const allowed = activeQueue === 'pending' ? PENDING_QUEUE_STATUSES : COMPLETED_QUEUE_STATUSES
      setGaps(res.data.filter((g) => allowed.has(g.status)))
    } catch {
      message.error('加载补全任务失败')
    }
    setLoading(false)
  }, [kbId, activeQueue, activeType, statusFilter])

  useEffect(() => {
    fetchGaps()
  }, [fetchGaps])

  // 当列表中存在 processing 状态的 gap 时，每 3 秒自动刷新
  useEffect(() => {
    const hasProcessing = gaps.some((g) => g.status === 'processing')
    if (!hasProcessing) return
    const timer = setInterval(fetchGaps, 3000)
    return () => clearInterval(timer)
  }, [gaps, fetchGaps])

  const invalidateAuditCache = (gapId: string) => {
    setAuditCache((prev) => {
      if (!prev[gapId]) return prev
      const next = { ...prev }
      delete next[gapId]
      return next
    })
  }

  const onStatus = async (gapId: string, status: string) => {
    if (!kbId) return
    try {
      await gapApi.updateStatus(kbId, gapId, status)
      message.success('状态已更新')
      invalidateAuditCache(gapId)
      fetchGaps()
    } catch {
      message.error('更新失败')
    }
  }

  const onDelete = async (gapId: string) => {
    if (!kbId) return
    try {
      await gapApi.delete(kbId, gapId)
      message.success('已删除')
      invalidateAuditCache(gapId)
      setSelectedRowKeys((prev) => prev.filter((k) => k !== gapId))
      fetchGaps()
    } catch {
      message.error('删除失败')
    }
  }

  const onBatchDelete = async () => {
    if (!kbId || selectedRowKeys.length === 0) return
    setBatchDeleting(true)
    try {
      const res = await gapApi.batchDelete(kbId, selectedRowKeys as string[])
      const { deleted, skipped } = res.data
      if (deleted > 0) {
        message.success(`已删除 ${deleted} 条补全任务`)
      }
      if (skipped > 0) {
        message.warning(`${skipped} 条未删除（可能正在入库中或不属于当前知识库）`)
      }
      for (const id of selectedRowKeys) {
        invalidateAuditCache(String(id))
      }
      setSelectedRowKeys([])
      fetchGaps()
    } catch {
      message.error('批量删除失败')
    }
    setBatchDeleting(false)
  }

  const renderDeleteButton = (gapId: string) => (
    <Popconfirm title={singleDeleteTitle} onConfirm={() => onDelete(gapId)}>
      <Button size="small" danger icon={<DeleteOutlined />} />
    </Popconfirm>
  )

  const onIngest = async (gap: KnowledgeGap, manual?: string) => {
    if (!kbId) return
    setIngestingId(gap.id)
    try {
      await gapApi.ingest(kbId, gap.id, manual ? { manual_content: manual } : undefined)
      message.success('已加入入库队列，后台处理中...')
      setManualModal(null)
      setManualContent('')
      invalidateAuditCache(gap.id)
      fetchGaps()
    } catch (e: unknown) {
      const err = e as {
        response?: { data?: { detail?: string | { msg?: string }[] } }
        message?: string
      }
      const detail = err.response?.data?.detail
      const text =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => (typeof d === 'object' && d?.msg ? d.msg : String(d))).join('; ')
            : err.message || '入库失败'
      message.error(text)
    }
    setIngestingId(null)
  }

  const onFollowUp = async () => {
    if (!kbId || !followUpModal || !followUpText.trim()) return
    setFollowUpLoading(true)
    try {
      await gapApi.followUp(kbId, followUpModal.id, { correction_text: followUpText.trim() })
      message.success('续补任务已创建，已切换到待处理')
      invalidateAuditCache(followUpModal.id)
      setFollowUpModal(null)
      setFollowUpText('')
      setActiveQueue('pending')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '创建续补失败')
    }
    setFollowUpLoading(false)
  }

  const loadAuditLog = async (gapId: string) => {
    if (!kbId || auditCache[gapId]) return
    setAuditLoadingId(gapId)
    try {
      const res = await gapApi.auditLog(kbId, gapId)
      setAuditCache((prev) => ({ ...prev, [gapId]: res.data }))
    } catch {
      message.error('加载处理记录失败')
    }
    setAuditLoadingId(null)
  }

  const renderAuditPanel = (gapId: string) => {
    if (auditLoadingId === gapId && !auditCache[gapId]) {
      return <Typography.Text type="secondary">加载处理记录…</Typography.Text>
    }
    const logs = auditCache[gapId]
    if (!logs) {
      return <Typography.Text type="secondary">展开以加载处理记录</Typography.Text>
    }
    if (logs.length === 0) {
      return <Typography.Text type="secondary">暂无处理记录</Typography.Text>
    }
    return (
      <Table
        size="small"
        rowKey="id"
        pagination={false}
        dataSource={logs}
        columns={[
          {
            title: '时间',
            dataIndex: 'created_at',
            width: 180,
            render: (v: string) => formatDateTime(v),
          },
          {
            title: '动作',
            dataIndex: 'action',
            width: 120,
            render: (a: string) => <Tag>{AUDIT_ACTION_LABEL[a] || a}</Tag>,
          },
          {
            title: '详情',
            dataIndex: 'detail',
            render: (d: string | null) => d || '—',
          },
        ]}
      />
    )
  }

  const openDocument = (documentId: string) => {
    if (!kbId) return
    navigate(`/knowledge-bases/${kbId}?tab=documents&doc=${documentId}`)
  }

  const openConversation = (conversationId: string) => {
    if (!kbId) return
    navigate(`/knowledge-bases/${kbId}/chat?conv=${conversationId}`)
  }

  const baseColumns: ColumnsType<KnowledgeGap> = [
    { title: '问题', dataIndex: 'query', ellipsis: true, width: 200 },
    {
      title: '类型',
      dataIndex: 'gap_type',
      width: 110,
      render: (t: string, row: KnowledgeGap) => (
        <Space direction="vertical" size={0}>
          <Tag>{GAP_TYPE_LABEL[t] || t}</Tag>
          {row.parent_gap_id && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              续补自 {row.parent_gap_id.slice(0, 8)}…
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: '建议内容',
      key: 'suggested',
      ellipsis: true,
      render: (_: unknown, row: KnowledgeGap) => {
        if (row.gap_type === 'KNOWLEDGE_ABSENT') {
          return <Typography.Text type="secondary">待人工添加（无 LLM 正文）</Typography.Text>
        }
        const s = parseSuggested(row.suggested_content)
        return s?.content ? (
          <Typography.Text ellipsis>
            {s.title ? `${s.title}: ` : ''}
            {s.content}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        )
      },
    },
    {
      title: '来源',
      dataIndex: 'source_ref',
      width: 120,
      ellipsis: true,
      render: (v: string | null) => v || '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 120,
      render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{STATUS_LABEL[s] || s}</Tag>,
    },
  ]

  const queueColumns: ColumnsType<KnowledgeGap> =
    activeQueue === 'completed'
      ? [
          {
            title: '完成时间',
            dataIndex: 'resolved_at',
            width: 180,
            render: (v: string | null) => (v ? formatDateTime(v) : '—'),
          },
          {
            title: '追溯',
            key: 'trace',
            width: 200,
            render: (_: unknown, row: KnowledgeGap) => (
              <Space wrap>
                {row.status === 'approved' && (
                  <Button
                    size="small"
                    type="link"
                    onClick={() => {
                      setFollowUpModal(row)
                      setFollowUpText('')
                    }}
                  >
                    续补
                  </Button>
                )}
                {row.document_id && (
                  <Button size="small" type="link" onClick={() => openDocument(row.document_id!)}>
                    查看文档
                  </Button>
                )}
                {row.conversation_id && (
                  <Button
                    size="small"
                    type="link"
                    onClick={() => openConversation(row.conversation_id!)}
                  >
                    查看对话
                  </Button>
                )}
                {!row.document_id && !row.conversation_id && row.status !== 'approved' && (
                  <Typography.Text type="secondary">—</Typography.Text>
                )}
              </Space>
            ),
          },
        ]
      : [
          {
            title: '创建时间',
            dataIndex: 'created_at',
            width: 180,
            render: (v: string) => formatDateTime(v),
          },
        ]

  const actionColumn: ColumnsType<KnowledgeGap> =
    activeQueue === 'pending'
      ? [
          {
            title: '操作',
            width: 300,
            render: (_: unknown, row: KnowledgeGap) => (
              <Space wrap>
                {row.status === 'processing' && (
                  <Tag color="processing">后台入库中，请稍后刷新...</Tag>
                )}
                {row.gap_type === 'KNOWLEDGE_ABSENT' && row.status === 'manual_required' && (
                  <Button
                    size="small"
                    variant="filled"
                    color="geekblue"
                    onClick={() => {
                      setManualModal(row)
                      setManualContent('')
                    }}
                  >
                    人工添加
                  </Button>
                )}
                {(row.gap_type === 'USER_PROVIDED' || row.gap_type === 'USER_CORRECTION') &&
                  ['suggested', 'pending'].includes(row.status) && (
                    <>
                      <Button
                        size="small"
                        variant="filled"
                        color="green"
                        loading={ingestingId === row.id}
                        disabled={!row.source_ref}
                        onClick={() => onIngest(row)}
                      >
                        批准入库
                      </Button>
                      <Popconfirm title="确定拒绝？" onConfirm={() => onStatus(row.id, 'rejected')}>
                        <Button size="small" variant="filled" color="danger">
                          拒绝
                        </Button>
                      </Popconfirm>
                    </>
                  )}
                {row.status === 'pending' && row.gap_type === 'RETRIEVAL_MISS' && (
                  <>
                    <Button
                      size="small"
                      variant="filled"
                      color="primary"
                      onClick={() => {
                        setManualModal(row)
                        setManualContent('')
                      }}
                    >
                      补全知识
                    </Button>
                    <Popconfirm title="确定拒绝？" onConfirm={() => onStatus(row.id, 'rejected')}>
                      <Button size="small" variant="filled" color="danger">
                        拒绝
                      </Button>
                    </Popconfirm>
                  </>
                )}
                {row.status !== 'processing' && renderDeleteButton(row.id)}
              </Space>
            ),
          },
        ]
      : [
          {
            title: '操作',
            width: 80,
            render: (_: unknown, row: KnowledgeGap) => renderDeleteButton(row.id),
          },
        ]

  const columns: ColumnsType<KnowledgeGap> = [...baseColumns, ...queueColumns, ...actionColumn]

  const queueTabItems = [
    { key: 'pending', label: '待处理' },
    { key: 'completed', label: '已完成' },
  ]

  const typeTabItems = [
    { key: 'all', label: '全部' },
    ...Object.entries(GAP_TYPE_LABEL).map(([k, label]) => ({ key: k, label })),
  ]

  const statusFilterOptions = Object.entries(STATUS_LABEL).filter(([value]) =>
    activeQueue === 'pending'
      ? PENDING_QUEUE_STATUSES.has(value)
      : COMPLETED_QUEUE_STATUSES.has(value),
  )

  const batchDeleteTitle =
    activeQueue === 'completed'
      ? `确定删除 ${selectedRowKeys.length} 条补全任务？不会删除已入库的文档内容。`
      : `确定删除 ${selectedRowKeys.length} 条补全任务？`

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/knowledge-bases/${kbId}`)}>
          返回知识库
        </Button>
        <Select
          style={{ width: 160 }}
          placeholder="按状态筛选"
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v)}
          options={statusFilterOptions.map(([value, label]) => ({ value, label }))}
        />
      </Space>
      <HudPanel>
        <h3 className="chart-panel__title">补全任务（Gap Queue）</h3>
        <Tabs
          activeKey={activeQueue}
          items={queueTabItems}
          onChange={(key) => {
            setActiveQueue(key as 'pending' | 'completed')
            setStatusFilter(undefined)
            setActiveType('all')
            setGaps([])
            setSelectedRowKeys([])
          }}
        />
        <Tabs activeKey={activeType} items={typeTabItems} onChange={setActiveType} />
        {selectedRowKeys.length > 0 && (
          <Space style={{ marginBottom: 12 }}>
            <Popconfirm title={batchDeleteTitle} onConfirm={onBatchDelete}>
              <Button size="small" danger loading={batchDeleting}>
                批量删除
              </Button>
            </Popconfirm>
            <Typography.Text type="secondary">已选 {selectedRowKeys.length} 项</Typography.Text>
          </Space>
        )}
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={gaps}
          pagination={{ pageSize: 10 }}
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
            getCheckboxProps: (record) => ({
              disabled: record.status === 'processing',
            }),
          }}
          expandable={
            activeQueue === 'completed'
              ? {
                  expandedRowRender: (row) => renderAuditPanel(row.id),
                  onExpand: (expanded, row) => {
                    if (expanded) void loadAuditLog(row.id)
                  },
                }
              : undefined
          }
        />
      </HudPanel>

      <Modal
        title="人工添加知识（KNOWLEDGE_ABSENT）"
        open={!!manualModal}
        onOk={() => manualModal && onIngest(manualModal, manualContent)}
        onCancel={() => {
          setManualModal(null)
          setManualContent('')
        }}
        okText="入库"
        okButtonProps={{ disabled: !manualContent.trim() }}
      >
        <Typography.Paragraph type="secondary">
          此类缺口禁止 LLM 自动生成正文，请填写用户确认后的内容。
        </Typography.Paragraph>
        <Input.TextArea
          rows={6}
          value={manualContent}
          onChange={(e) => setManualContent(e.target.value)}
          placeholder="输入要入库的知识正文…"
        />
      </Modal>

      <Modal
        title="续补知识"
        open={!!followUpModal}
        confirmLoading={followUpLoading}
        onOk={onFollowUp}
        onCancel={() => {
          setFollowUpModal(null)
          setFollowUpText('')
        }}
        okText="创建续补任务"
        okButtonProps={{ disabled: !followUpText.trim() }}
      >
        <Typography.Paragraph type="secondary">
          基于已入库内容继续补充或修正，将生成新的待处理工单。
        </Typography.Paragraph>
        {followUpModal && (
          <Typography.Paragraph>原问题：{followUpModal.query}</Typography.Paragraph>
        )}
        <Input.TextArea
          rows={5}
          value={followUpText}
          onChange={(e) => setFollowUpText(e.target.value)}
          placeholder="输入补充/修正正文…"
        />
      </Modal>
    </div>
  )
}
