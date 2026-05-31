import { useCallback, useEffect, useState } from 'react'
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
import { ArrowLeftOutlined } from '@ant-design/icons'
import { gapApi, type KnowledgeGap } from '../api/gap'
import HudPanel from '../components/common/HudPanel'
import { formatDateTime } from '../utils/format'

const GAP_TYPE_LABEL: Record<string, string> = {
  RETRIEVAL_MISS: '检索未命中',
  USER_PROVIDED: '用户提供',
  USER_CORRECTION: '用户纠正',
  KNOWLEDGE_ABSENT: '知识缺失',
}

const STATUS_LABEL: Record<string, string> = {
  pending: '待处理',
  suggested: '待审批',
  approved: '已入库',
  rejected: '已拒绝',
  manual_required: '待人工添加',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'gold',
  suggested: 'blue',
  approved: 'green',
  rejected: 'red',
  manual_required: 'orange',
}

function parseSuggested(raw: string | null): { title?: string; content?: string } | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as { title?: string; content?: string }
  } catch {
    return { content: raw }
  }
}

export default function GapTasks() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [gaps, setGaps] = useState<KnowledgeGap[]>([])
  const [loading, setLoading] = useState(false)
  const [activeType, setActiveType] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [manualModal, setManualModal] = useState<KnowledgeGap | null>(null)
  const [manualContent, setManualContent] = useState('')
  const [ingestingId, setIngestingId] = useState<string | null>(null)

  const fetchGaps = useCallback(async () => {
    if (!kbId) return
    setLoading(true)
    try {
      const params: { gap_type?: string; status?: string } = {}
      if (activeType !== 'all') params.gap_type = activeType
      if (statusFilter) params.status = statusFilter
      const res = await gapApi.list(kbId, params)
      setGaps(res.data)
    } catch {
      message.error('加载补全任务失败')
    }
    setLoading(false)
  }, [kbId, activeType, statusFilter])

  useEffect(() => {
    fetchGaps()
  }, [fetchGaps])

  const onStatus = async (gapId: string, status: string) => {
    if (!kbId) return
    try {
      await gapApi.updateStatus(kbId, gapId, status)
      message.success('状态已更新')
      fetchGaps()
    } catch {
      message.error('更新失败')
    }
  }

  const onIngest = async (gap: KnowledgeGap, manual?: string) => {
    if (!kbId) return
    setIngestingId(gap.id)
    try {
      const res = await gapApi.ingest(kbId, gap.id, manual ? { manual_content: manual } : undefined)
      const { ingest_allowed, ingest_duplicates, ingest_conflicts } = res.data
      if (ingest_allowed > 0) {
        message.success(`已入库（${ingest_allowed} 块通过门禁）`)
      } else {
        message.warning(
          `未新增内容块（重复 ${ingest_duplicates}，冲突 ${ingest_conflicts}）。请改写后再试。`,
        )
      }
      setManualModal(null)
      setManualContent('')
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

  const columns = [
    { title: '问题', dataIndex: 'query', ellipsis: true, width: 200 },
    {
      title: '类型',
      dataIndex: 'gap_type',
      width: 110,
      render: (t: string) => <Tag>{GAP_TYPE_LABEL[t] || t}</Tag>,
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
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => formatDateTime(v),
    },
    {
      title: '操作',
      width: 260,
      render: (_: unknown, row: KnowledgeGap) => (
        <Space wrap>
          {row.gap_type === 'KNOWLEDGE_ABSENT' && row.status === 'manual_required' && (
            <Button
              size="small"
              type="primary"
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
                  type="primary"
                  loading={ingestingId === row.id}
                  disabled={!row.source_ref}
                  onClick={() => onIngest(row)}
                >
                  批准入库
                </Button>
                <Popconfirm title="确定拒绝？" onConfirm={() => onStatus(row.id, 'rejected')}>
                  <Button size="small" danger>
                    拒绝
                  </Button>
                </Popconfirm>
              </>
            )}
          {row.status === 'pending' && row.gap_type === 'RETRIEVAL_MISS' && (
            <>
              <Button
                size="small"
                type="primary"
                onClick={() => {
                  setManualModal(row)
                  setManualContent('')
                }}
              >
                补全知识
              </Button>
              <Popconfirm title="确定拒绝？" onConfirm={() => onStatus(row.id, 'rejected')}>
                <Button size="small" danger>
                  拒绝
                </Button>
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ]

  const tabItems = [
    { key: 'all', label: '全部' },
    ...Object.entries(GAP_TYPE_LABEL).map(([k, label]) => ({ key: k, label })),
  ]

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
          onChange={(v) => setStatusFilter(v)}
          options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))}
        />
      </Space>
      <HudPanel>
        <h3 className="chart-panel__title">补全任务（Gap Queue）</h3>
        <Tabs activeKey={activeType} items={tabItems} onChange={setActiveType} />
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={gaps}
          pagination={{ pageSize: 10 }}
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
    </div>
  )
}
