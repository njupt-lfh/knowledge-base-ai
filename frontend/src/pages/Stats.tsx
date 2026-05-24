import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Table, Typography, Tag, Space } from 'antd'
import { FireOutlined, FileTextOutlined, DatabaseOutlined, EyeOutlined } from '@ant-design/icons'
import request from '../api/request'

interface HotItem {
  chunk_id: string
  content: string
  hit_count: number
  chunk_index: number
  document_id: string
}

interface KBStats {
  document_count: number
  chunk_count: number
  total_hits: number
  hot_items: HotItem[]
}

export default function Stats() {
  const [kbs, setKbs] = useState<{ id: string; name: string }[]>([])
  const [selectedKb, setSelectedKb] = useState<string | null>(null)
  const [stats, setStats] = useState<KBStats | null>(null)
  const [overview, setOverview] = useState<Record<string, number>>({})

  useEffect(() => {
    request.get('/api/knowledge-bases').then((r) => setKbs(r.data.items || []))
    request.get('/api/stats/overview').then((r) => setOverview(r.data))
  }, [])

  const loadStats = async (kbId: string) => {
    setSelectedKb(kbId)
    const r = await request.get(`/api/knowledge-bases/${kbId}/stats`)
    setStats(r.data)
  }

  // Progress bar using div
  const maxHits = stats?.hot_items[0]?.hit_count || 1

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Card title="全局概览">
        <Row gutter={24}>
          <Col span={6}>
            <Statistic title="知识库" value={overview.kb_count || 0} prefix={<DatabaseOutlined />} />
          </Col>
          <Col span={6}>
            <Statistic title="文档总数" value={overview.doc_count || 0} prefix={<FileTextOutlined />} />
          </Col>
          <Col span={6}>
            <Statistic title="知识块" value={overview.chunk_count || 0} prefix={<DatabaseOutlined />} />
          </Col>
          <Col span={6}>
            <Statistic title="总命中次数" value={overview.total_hits || 0} prefix={<EyeOutlined />} />
          </Col>
        </Row>
      </Card>

      <Card
        title={
          <Space>
            <FireOutlined style={{ color: '#ff4d4f' }} />
            知识热度排行
            <Typography.Text type="secondary">（点击知识库查看详情）</Typography.Text>
          </Space>
        }
      >
        <Space wrap style={{ marginBottom: 16 }}>
          {kbs.map((kb) => (
            <Tag
              key={kb.id}
              color={selectedKb === kb.id ? 'blue' : 'default'}
              style={{ cursor: 'pointer', padding: '4px 12px' }}
              onClick={() => loadStats(kb.id)}
            >
              {kb.name}
            </Tag>
          ))}
        </Space>

        {stats && stats.hot_items.length > 0 && (
          <Table
            rowKey="chunk_id"
            dataSource={stats.hot_items}
            pagination={false}
            size="small"
            columns={[
              { title: '排名', key: 'rank', width: 60, render: (_, __, i) => `#${i + 1}` },
              {
                title: '热度', dataIndex: 'hit_count', key: 'hits', width: 220,
                render: (v: number) => (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{
                      height: 16,
                      width: `${Math.max(10, (v / maxHits) * 160)}px`,
                      background: `linear-gradient(90deg, #ff4d4f, #ff7a45)`,
                      borderRadius: 8,
                      transition: 'width 0.5s',
                    }} />
                    <Typography.Text strong>{v} 次</Typography.Text>
                  </div>
                ),
              },
              {
                title: '内容预览', dataIndex: 'content', key: 'content',
                render: (v: string) => (
                  <Typography.Paragraph ellipsis={{ rows: 1 }} style={{ margin: 0 }}>
                    {v}
                  </Typography.Paragraph>
                ),
              },
            ]}
          />
        )}

        {stats && stats.hot_items.length === 0 && (
          <Typography.Text type="secondary">暂无命中数据，请先使用检索或对话功能</Typography.Text>
        )}

        {stats && (
          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={8}>
              <Statistic title="文档数" value={stats.document_count} />
            </Col>
            <Col span={8}>
              <Statistic title="知识块" value={stats.chunk_count} />
            </Col>
            <Col span={8}>
              <Statistic title="总命中" value={stats.total_hits} />
            </Col>
          </Row>
        )}
      </Card>
    </Space>
  )
}
