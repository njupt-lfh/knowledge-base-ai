/**
 * 入库冲突裁决面板
 * 展示待处理相似度冲突并支持保留新/旧内容或忽略
 * 主要导出：默认 ConflictsPanel 组件
 */
import { useCallback, useEffect, useState } from 'react'
import { Button, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import { ReloadOutlined, WarningOutlined } from '@ant-design/icons'
import type { GovernanceChunkRef } from '../../api/governance'
import { conflictsApi, type KnowledgeConflict } from '../../api/conflicts'
import './ConflictsPanel.css'

interface ConflictsPanelProps {
  kbId: string
  /** 在文档知识块抽屉中定位到指定块；chunkId 省略时仅打开来源文档 */
  onLocateChunk?: (documentId: string, chunkId?: string) => void
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

/** 知识库详情「入库冲突」Tab：LLM 矛盾检测队列 */
export default function ConflictsPanel({ kbId, onLocateChunk }: ConflictsPanelProps) {
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
        <Space direction="vertical" size={8} className="conflicts-panel__compare">
          <ConflictChunkSource
            label="已有："
            preview={row.existing_preview}
            refInfo={row.existing_chunk_ref}
            onLocate={
              row.existing_chunk_ref && onLocateChunk
                ? () =>
                    onLocateChunk(
                      row.existing_chunk_ref!.document_id,
                      row.existing_chunk_ref!.chunk_id,
                    )
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
