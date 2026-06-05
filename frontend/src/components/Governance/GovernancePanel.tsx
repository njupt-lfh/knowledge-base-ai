/**
 * 知识库治理建议面板（Phase 3 治理闭环）
 * 扫描并持久化建议，走 pending → approved → executed → verified 状态机
 * 主要导出：默认 GovernancePanel 组件
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { ColumnsType } from 'antd/es/table'
import type { TablePaginationConfig } from 'antd/es/table/interface'
import {
  Button,
  Card,
  Popconfirm,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CheckOutlined,
  CloseOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ScanOutlined,
} from '@ant-design/icons'
import ColdKnowledgeBadge from '../Charts/ColdKnowledgeBadge'
import {
  governanceApi,
  type AuditLogEntry,
  type GovernanceHealth,
  type GovernanceStatusCounts,
  type PersistedSuggestion,
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

const STATUS_LABELS: Record<string, string> = {
  pending: '待审核',
  approved: '已批准',
  executed: '已执行',
  verified: '已验证',
  dismissed: '已驳回',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'gold',
  approved: 'blue',
  executed: 'purple',
  verified: 'green',
  dismissed: 'default',
}

const SEVERITY_COLOR: Record<string, string> = {
  info: 'blue',
  warning: 'orange',
  error: 'red',
}

const ACTION_LABELS: Record<string, string> = {
  archive: '归档',
  deactivate: '禁用',
  boost_faq: '提升FAQ',
  merge: '合并',
}

const PENDING_PAGE_SIZE = 10
const WORKFLOW_FETCH_LIMIT = 200

const AUDIT_ACTION_LABELS: Record<string, string> = {
  approved: '批准',
  dismissed: '驳回',
  executed: '执行',
  verified: '验证',
  reverted: '已回退',
}

interface GovernancePanelProps {
  kbId: string
  onApplied?: () => void
}

function parseChunkIds(raw: string): string[] {
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

/**
 * 知识库详情「治理建议」Tab 内容
 * @param onApplied 治理动作成功后通知父组件刷新健康度/冷知识统计
 */
export default function GovernancePanel({ kbId, onApplied }: GovernancePanelProps) {
  const [activeTab, setActiveTab] = useState('pending')
  const [health, setHealth] = useState<GovernanceHealth | null>(null)
  const [pendingRows, setPendingRows] = useState<PersistedSuggestion[]>([])
  const [pendingPage, setPendingPage] = useState(1)
  const [workflowRows, setWorkflowRows] = useState<PersistedSuggestion[]>([])
  const [statusCounts, setStatusCounts] = useState<GovernanceStatusCounts>({})
  const [auditRows, setAuditRows] = useState<AuditLogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [actingId, setActingId] = useState<string | null>(null)
  const [auditFilter, setAuditFilter] = useState<string | undefined>(undefined)
  const tableWrapRef = useRef<HTMLDivElement>(null)
  const [tableScrollY, setTableScrollY] = useState(280)

  const pendingTotal = statusCounts.pending ?? 0
  const workflowTotal =
    (statusCounts.approved ?? 0) + (statusCounts.executed ?? 0) + (statusCounts.verified ?? 0)

  const fetchCounts = useCallback(async () => {
    try {
      const res = await governanceApi.statusCounts(kbId)
      setStatusCounts(res.data)
      return
    } catch {
      /* counts 接口不可用时，分页累加（需后端支持 offset） */
    }
    const statuses = ['pending', 'approved', 'dismissed', 'executed', 'verified'] as const
    const counts: GovernanceStatusCounts = Object.fromEntries(statuses.map((k) => [k, 0]))
    for (const status of statuses) {
      let offset = 0
      const limit = 200
      let seenFirstId: string | undefined
      for (let page = 0; page < 200; page++) {
        const res = await governanceApi.listPersisted(kbId, { status, limit, offset })
        const batch = res.data.items
        if (batch.length === 0) break
        if (page > 0 && batch[0]?.id === seenFirstId) break
        seenFirstId ??= batch[0]?.id
        counts[status] = (counts[status] ?? 0) + batch.length
        if (res.data.total > 0 && (counts[status] ?? 0) >= res.data.total) {
          counts[status] = res.data.total
          break
        }
        if (batch.length < limit) break
        offset += limit
      }
    }
    setStatusCounts(counts)
  }, [kbId])

  const measureTableScroll = useCallback(() => {
    const wrap = tableWrapRef.current
    if (!wrap) return
    const pagination = wrap.querySelector<HTMLElement>('.ant-table-pagination')
    const thead = wrap.querySelector<HTMLElement>('.ant-table-thead')
    const reserved = (pagination?.offsetHeight ?? 52) + (thead?.offsetHeight ?? 39) + 12
    setTableScrollY(Math.max(120, wrap.clientHeight - reserved))
  }, [])

  useEffect(() => {
    measureTableScroll()
    const wrap = tableWrapRef.current
    if (!wrap) return
    const ro = new ResizeObserver(() => measureTableScroll())
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [activeTab, loading, measureTableScroll, pendingTotal, workflowTotal, auditRows.length])

  useEffect(() => {
    if (loading) return
    const id = window.requestAnimationFrame(() => measureTableScroll())
    return () => window.cancelAnimationFrame(id)
  }, [loading, activeTab, measureTableScroll, pendingTotal, workflowTotal, auditRows.length])

  const fetchPending = useCallback(
    async (page = 1) => {
      const loadPage = (targetPage: number) =>
        governanceApi.listPersisted(kbId, {
          status: 'pending',
          limit: PENDING_PAGE_SIZE,
          offset: (targetPage - 1) * PENDING_PAGE_SIZE,
        })

      let res = await loadPage(page)
      let targetPage = page
      if (res.data.total > 0) {
        const maxPage = Math.max(1, Math.ceil(res.data.total / PENDING_PAGE_SIZE))
        targetPage = Math.min(page, maxPage)
        if (targetPage !== page) {
          res = await loadPage(targetPage)
        }
      }
      setPendingPage(targetPage)
      setPendingRows(res.data.items)
    },
    [kbId],
  )

  const fetchWorkflow = useCallback(async () => {
    const [approved, executed, verified] = await Promise.all([
      governanceApi.listPersisted(kbId, { status: 'approved', limit: WORKFLOW_FETCH_LIMIT }),
      governanceApi.listPersisted(kbId, { status: 'executed', limit: WORKFLOW_FETCH_LIMIT }),
      governanceApi.listPersisted(kbId, { status: 'verified', limit: WORKFLOW_FETCH_LIMIT }),
    ])
    setWorkflowRows([...approved.data.items, ...executed.data.items, ...verified.data.items])
  }, [kbId])

  const fetchAudit = useCallback(async () => {
    const res = await governanceApi.auditLog(kbId, {
      action: auditFilter,
      limit: 100,
    })
    setAuditRows(res.data)
  }, [kbId, auditFilter])

  const refreshAll = useCallback(async () => {
    setLoading(true)
    try {
      await Promise.all([fetchCounts(), fetchPending(pendingPage), fetchWorkflow(), fetchAudit()])
    } catch {
      message.error('加载治理数据失败')
    }
    setLoading(false)
  }, [fetchCounts, fetchPending, fetchWorkflow, fetchAudit, pendingPage])

  useEffect(() => {
    refreshAll()
  }, [refreshAll])

  const handleScanAndPersist = async () => {
    setLoading(true)
    try {
      const res = await governanceApi.scanAndPersist(kbId, false)
      setHealth(res.data.health)
      message.success(`扫描完成，新增 ${res.data.new_suggestions} 条待审核建议`)
      await Promise.all([fetchCounts(), fetchPending(1)])
      onApplied?.()
    } catch {
      message.error('扫描并入库失败')
    }
    setLoading(false)
  }

  const handleRollback = async (suggestionId: string) => {
    setActingId(suggestionId)
    try {
      const res = await governanceApi.rollback(kbId, suggestionId)
      const from = STATUS_LABELS[res.data.prev_status] || res.data.prev_status
      const to = STATUS_LABELS[res.data.status] || res.data.status
      message.success(`已回退: ${from} → ${to}`)
      await Promise.all([fetchCounts(), fetchPending(pendingPage), fetchWorkflow(), fetchAudit()])
    } catch {
      message.error('回退失败（仅已批准/已执行状态可回退）')
    }
    setActingId(null)
  }

  const patchListsAfterAction = (
    suggestionId: string,
    action: 'approve' | 'dismiss' | 'execute' | 'verify',
  ) => {
    const pending = pendingRows.find((r) => r.id === suggestionId)
    const workflow = workflowRows.find((r) => r.id === suggestionId)
    const now = new Date().toISOString()

    if (action === 'approve' && pending) {
      setPendingRows((prev) => prev.filter((r) => r.id !== suggestionId))
      setStatusCounts((c) => ({
        ...c,
        pending: Math.max(0, (c.pending ?? 0) - 1),
        approved: (c.approved ?? 0) + 1,
      }))
      setWorkflowRows((prev) => [...prev, { ...pending, status: 'approved', approved_at: now }])
      return
    }
    if (action === 'dismiss' && pending) {
      setPendingRows((prev) => prev.filter((r) => r.id !== suggestionId))
      setStatusCounts((c) => ({
        ...c,
        pending: Math.max(0, (c.pending ?? 0) - 1),
        dismissed: (c.dismissed ?? 0) + 1,
      }))
      return
    }
    if (action === 'execute' && workflow) {
      setWorkflowRows((prev) =>
        prev.map((r) =>
          r.id === suggestionId ? { ...r, status: 'executed', executed_at: now } : r,
        ),
      )
      return
    }
    if (action === 'verify' && workflow) {
      setWorkflowRows((prev) =>
        prev.map((r) =>
          r.id === suggestionId ? { ...r, status: 'verified', verified_at: now } : r,
        ),
      )
    }
  }

  const runAction = async (
    suggestionId: string,
    action: 'approve' | 'dismiss' | 'execute' | 'verify',
    successMsg: string,
  ) => {
    setActingId(suggestionId)
    try {
      if (action === 'approve') await governanceApi.approve(kbId, suggestionId)
      else if (action === 'dismiss') await governanceApi.dismiss(kbId, suggestionId)
      else if (action === 'execute') await governanceApi.execute(kbId, suggestionId)
      else await governanceApi.verify(kbId, suggestionId)
      patchListsAfterAction(suggestionId, action)
      message.success(successMsg)
      onApplied?.()
      await Promise.all([fetchCounts(), fetchPending(pendingPage), fetchWorkflow(), fetchAudit()])
    } catch {
      message.error('操作失败')
    }
    setActingId(null)
  }

  const suggestionColumns = [
    {
      title: '类型',
      dataIndex: 'suggestion_type',
      width: 120,
      render: (t: string) => <Tag>{TYPE_LABELS[t] || t}</Tag>,
    },
    {
      title: '建议',
      key: 'title',
      render: (_: unknown, row: PersistedSuggestion) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{row.title}</Typography.Text>
          <Typography.Text type="secondary">{row.description}</Typography.Text>
          {row.content_preview && (
            <Typography.Text type="secondary" className="gov-preview">
              {row.content_preview}
            </Typography.Text>
          )}
          <Typography.Text type="secondary" className="gov-chunk-ids">
            块 ID：{parseChunkIds(row.chunk_ids).join(', ') || '—'}
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
      title: '推荐动作',
      dataIndex: 'recommended_action',
      width: 100,
      render: (a: string) => ACTION_LABELS[a] || a,
    },
  ]

  const pendingColumns = [
    ...suggestionColumns,
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, row: PersistedSuggestion) => (
        <Space size="small">
          <Button
            size="small"
            type="primary"
            icon={<CheckOutlined />}
            loading={actingId === row.id}
            onClick={() => runAction(row.id, 'approve', '已批准')}
          >
            批准
          </Button>
          <Popconfirm
            title="确定驳回此建议？"
            onConfirm={() => runAction(row.id, 'dismiss', '已驳回')}
          >
            <Button size="small" danger icon={<CloseOutlined />} loading={actingId === row.id}>
              驳回
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const workflowColumns = [
    ...suggestionColumns,
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] || 'default'}>{STATUS_LABELS[s] || s}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, row: PersistedSuggestion) => {
        if (row.status === 'approved') {
          return (
            <Space size="small">
              <Popconfirm
                title="确定执行此治理动作？"
                onConfirm={() => runAction(row.id, 'execute', '已执行')}
              >
                <Button
                  size="small"
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  loading={actingId === row.id}
                >
                  执行
                </Button>
              </Popconfirm>
              <Popconfirm title="确定回退到待审核？" onConfirm={() => handleRollback(row.id)}>
                <Button size="small" loading={actingId === row.id}>
                  回退
                </Button>
              </Popconfirm>
            </Space>
          )
        }
        if (row.status === 'executed') {
          return (
            <Space size="small">
              <Button
                size="small"
                type="primary"
                icon={<SafetyCertificateOutlined />}
                loading={actingId === row.id}
                onClick={() => runAction(row.id, 'verify', '已验证')}
              >
                验证
              </Button>
              <Popconfirm
                title="确定回退到已批准？（会恢复 chunk）"
                onConfirm={() => handleRollback(row.id)}
              >
                <Button size="small" loading={actingId === row.id}>
                  回退
                </Button>
              </Popconfirm>
            </Space>
          )
        }
        return <Typography.Text type="secondary">—</Typography.Text>
      },
    },
  ]

  const auditColumns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 160,
      render: (t: string) => new Date(t).toLocaleString(),
    },
    {
      title: '动作',
      dataIndex: 'action',
      width: 80,
      render: (a: string) => <Tag>{AUDIT_ACTION_LABELS[a] || a}</Tag>,
    },
    {
      title: '建议 ID',
      dataIndex: 'suggestion_id',
      width: 100,
      render: (id: string | null) => (id ? `${id.slice(0, 8)}…` : '—'),
    },
    {
      title: '操作人',
      dataIndex: 'operator',
      width: 80,
      render: (o: string | null) => o || '—',
    },
    {
      title: '详情',
      dataIndex: 'detail',
      render: (d: string | null) => d || '—',
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, row: AuditLogEntry) => {
        if (!row.suggestion_id) return <Typography.Text type="secondary">—</Typography.Text>
        return (
          <Popconfirm
            title="确定撤销此操作？会将工单回退到上一个状态"
            onConfirm={() => handleRollback(row.suggestion_id!)}
          >
            <Button size="small" danger loading={actingId === row.suggestion_id}>
              撤销
            </Button>
          </Popconfirm>
        )
      },
    },
  ]

  const coldBadge: ColdKnowledgeStats | null = health
    ? {
        cold_count_90d: health.cold_count_90d,
        cold_count_total: health.cold_count_total,
        threshold_days: health.threshold_days,
      }
    : null

  const tableScroll = { y: tableScrollY }

  const renderTablePane = <T extends { id: string }>(
    tabKey: string,
    emptyHint: string | null,
    columns: ColumnsType<T>,
    dataSource: T[],
    pagination: TablePaginationConfig | false,
    toolbar?: ReactNode,
  ) => (
    <div className="governance-panel__tab-body">
      {toolbar}
      {emptyHint && (dataSource?.length ?? 0) === 0 && !loading && (
        <Typography.Text type="secondary" className="governance-panel__empty">
          {emptyHint}
        </Typography.Text>
      )}
      <div
        ref={tabKey === activeTab ? tableWrapRef : undefined}
        className="governance-panel__table-wrap"
      >
        <Table<T>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={dataSource ?? []}
          pagination={pagination === false ? false : { showSizeChanger: false, ...pagination }}
          size="small"
          scroll={tableScroll}
        />
      </div>
    </div>
  )

  const tabItems = useMemo(
    () => [
      {
        key: 'pending',
        label: `待审核 (${pendingTotal})`,
        children: renderTablePane(
          'pending',
          '暂无待审核建议，点击「扫描并入库」生成工单',
          pendingColumns,
          pendingRows,
          {
            current: pendingPage,
            pageSize: PENDING_PAGE_SIZE,
            total: pendingTotal,
            onChange: (page) => {
              void fetchPending(page)
            },
          },
        ),
      },
      {
        key: 'workflow',
        label: `执行流转 (${workflowTotal})`,
        children: renderTablePane('workflow', '暂无流转中的建议', workflowColumns, workflowRows, {
          pageSize: 10,
          total: workflowRows?.length ?? 0,
        }),
      },
      {
        key: 'audit',
        label: '审计日志',
        children: renderTablePane(
          'audit',
          null,
          auditColumns,
          auditRows,
          { pageSize: 15 },
          <Space className="governance-panel__audit-filter" wrap>
            <Typography.Text type="secondary">筛选动作：</Typography.Text>
            <Select
              allowClear
              placeholder="全部"
              style={{ width: 120 }}
              value={auditFilter}
              onChange={(v) => setAuditFilter(v)}
              options={Object.entries(AUDIT_ACTION_LABELS).map(([k, v]) => ({
                value: k,
                label: v,
              }))}
            />
          </Space>,
        ),
      },
    ],
    [
      pendingTotal,
      workflowTotal,
      pendingPage,
      pendingRows,
      workflowRows,
      auditRows,
      auditFilter,
      loading,
      activeTab,
      fetchPending,
      pendingColumns,
      workflowColumns,
      auditColumns,
    ],
  )

  return (
    <div className="governance-panel">
      <div className="governance-panel__head">
        <Space wrap align="center" className="governance-panel__toolbar">
          <ColdKnowledgeBadge data={coldBadge} />
          {health && (
            <Card size="small" className="governance-panel__stat">
              <Typography.Text type="secondary">活跃块 </Typography.Text>
              <Typography.Text strong>{health.active_chunks}</Typography.Text>
              <Typography.Text type="secondary"> / {health.total_chunks}</Typography.Text>
            </Card>
          )}
          <Card size="small" className="governance-panel__stat">
            <Typography.Text type="secondary">待审核 </Typography.Text>
            <Typography.Text strong>{pendingTotal}</Typography.Text>
          </Card>
          <Button
            type="primary"
            icon={<ScanOutlined />}
            onClick={handleScanAndPersist}
            loading={loading}
          >
            扫描并入库
          </Button>
          <Button icon={<ReloadOutlined />} onClick={refreshAll} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      <Tabs
        key={`gov-tabs-${pendingTotal}-${workflowTotal}`}
        className="governance-panel__tabs"
        activeKey={activeTab}
        onChange={setActiveTab}
        destroyOnHidden={false}
        items={tabItems}
      />
    </div>
  )
}
