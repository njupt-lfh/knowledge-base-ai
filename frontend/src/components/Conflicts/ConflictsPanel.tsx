import { useCallback, useEffect, useState } from 'react'
import { Button, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import { ReloadOutlined, WarningOutlined } from '@ant-design/icons'
import { conflictsApi, type KnowledgeConflict } from '../../api/conflicts'
import './ConflictsPanel.css'

interface ConflictsPanelProps {
  kbId: string
}

export default function ConflictsPanel({ kbId }: ConflictsPanelProps) {
  const [rows, setRows] = useState<KnowledgeConflict[]>([])
  const [loading, setLoading] = useState(false)
  const [resolvingId, setResolvingId] = useState<string | null>(null)

  const fetchRows = useCallback(async () => {
    setLoading(true)
    try {
      const res = await conflictsApi.list(kbId)
      setRows(res.data)
    } catch {
      message.error('获取冲突列表失败')
    }
    setLoading(false)
  }, [kbId])

  useEffect(() => {
    fetchRows()
  }, [fetchRows])

  const resolve = async (id: string, resolution: string) => {
    setResolvingId(id)
    try {
      await conflictsApi.resolve(kbId, id, resolution)
      message.success('已裁决')
      fetchRows()
    } catch {
      message.error('裁决失败')
    }
    setResolvingId(null)
  }

  const columns = [
    {
      title: '相似度',
      dataIndex: 'similarity',
      width: 90,
      render: (v: number) => <Tag color="orange">{v}</Tag>,
    },
    {
      title: '已有 / 待入库',
      key: 'content',
      render: (_: unknown, row: KnowledgeConflict) => (
        <Space direction="vertical" size={4} className="conflicts-panel__compare">
          <Typography.Text type="secondary">已有：{row.existing_preview}</Typography.Text>
          <Typography.Text>待入库：{row.new_preview}</Typography.Text>
          {row.llm_reason && (
            <Typography.Text type="danger" className="conflicts-panel__reason">
              {row.llm_reason}
            </Typography.Text>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_: unknown, row: KnowledgeConflict) => (
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
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space wrap>
        <Typography.Text type="secondary">
          <WarningOutlined /> 0.75–0.92 相似度区间经 LLM 矛盾检测（最多 3 次/块）
        </Typography.Text>
        <Button icon={<ReloadOutlined />} onClick={fetchRows} loading={loading}>
          刷新
        </Button>
      </Space>
      {rows.length === 0 && !loading && (
        <Typography.Text type="secondary">暂无待裁决冲突</Typography.Text>
      )}
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={rows}
        pagination={{ pageSize: 8 }}
      />
    </Space>
  )
}
