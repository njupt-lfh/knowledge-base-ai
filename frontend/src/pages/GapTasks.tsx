import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, message, Select, Space, Table, Tag, Tabs } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { gapApi, type KnowledgeGap } from '../api/gap'
import HudPanel from '../components/common/HudPanel'

const GAP_TYPE_LABEL: Record<string, string> = {
  RETRIEVAL_MISS: '检索未命中',
  USER_PROVIDED: '用户提供',
  USER_CORRECTION: '用户纠正',
  KNOWLEDGE_ABSENT: '知识缺失',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'gold',
  suggested: 'blue',
  approved: 'green',
  rejected: 'red',
  manual_required: 'orange',
}

export default function GapTasks() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [gaps, setGaps] = useState<KnowledgeGap[]>([])
  const [loading, setLoading] = useState(false)
  const [activeType, setActiveType] = useState<string>('all')

  const fetchGaps = useCallback(async () => {
    if (!kbId) return
    setLoading(true)
    try {
      const params = activeType === 'all' ? {} : { gap_type: activeType }
      const res = await gapApi.list(kbId, params)
      setGaps(res.data)
    } catch {
      message.error('加载补全任务失败')
    }
    setLoading(false)
  }, [kbId, activeType])

  useEffect(() => { fetchGaps() }, [fetchGaps])

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

  const columns = [
    { title: '问题', dataIndex: 'query', ellipsis: true },
    {
      title: '类型',
      dataIndex: 'gap_type',
      width: 120,
      render: (t: string) => <Tag>{GAP_TYPE_LABEL[t] || t}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 130,
      render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', width: 180 },
    {
      title: '操作',
      width: 220,
      render: (_: unknown, row: KnowledgeGap) => (
        <Space>
          {row.status === 'pending' && (
            <>
              <Button size="small" type="link" onClick={() => onStatus(row.id, 'approved')}>通过</Button>
              <Button size="small" type="link" danger onClick={() => onStatus(row.id, 'rejected')}>拒绝</Button>
            </>
          )}
          {row.gap_type === 'KNOWLEDGE_ABSENT' && row.status === 'manual_required' && (
            <Button size="small" type="link" onClick={() => onStatus(row.id, 'pending')}>转待处理</Button>
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
          onChange={(v) => fetchGaps()}
          options={[
            { value: 'pending', label: 'pending' },
            { value: 'manual_required', label: 'manual_required' },
            { value: 'suggested', label: 'suggested' },
          ]}
        />
      </Space>
      <HudPanel title="补全任务（Gap Queue）">
        <Tabs activeKey={activeType} items={tabItems} onChange={setActiveType} />
        <Table rowKey="id" loading={loading} columns={columns} dataSource={gaps} pagination={{ pageSize: 10 }} />
      </HudPanel>
    </div>
  )
}
