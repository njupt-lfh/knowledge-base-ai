import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Table, Button, Space, Upload, message, Tabs, Input, Switch, Popconfirm } from 'antd'
import { UploadOutlined, PlusOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons'
import { knowledgeApi } from '../api/knowledge'
import { documentApi } from '../api/document'
import type { KnowledgeBase, Document } from '../types'

export default function KnowledgeDetail() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [manualModal, setManualModal] = useState(false)
  const [manualTitle, setManualTitle] = useState('')
  const [manualContent, setManualContent] = useState('')

  const fetchKb = async () => {
    if (!kbId) return
    try {
      const res = await knowledgeApi.getById(kbId)
      setKb(res.data)
    } catch { message.error('获取知识库详情失败') }
  }

  const fetchDocs = async () => {
    if (!kbId) return
    setLoading(true)
    try {
      const res = await documentApi.list(kbId)
      setDocs(res.data.items)
    } catch { message.error('获取文档列表失败') }
    setLoading(false)
  }

  useEffect(() => { fetchKb(); fetchDocs() }, [kbId])

  const handleUpload = async (file: File) => {
    if (!kbId) return
    try {
      await documentApi.upload(kbId, file)
      message.success('上传成功，正在处理中...')
      fetchDocs()
    } catch { message.error('上传失败') }
  }

  const handleManualCreate = async () => {
    if (!kbId || !manualTitle || !manualContent) return
    try {
      await documentApi.createManual(kbId, { title: manualTitle, content: manualContent })
      message.success('录入成功')
      setManualModal(false)
      setManualTitle('')
      setManualContent('')
      fetchDocs()
    } catch { message.error('录入失败') }
  }

  const handleDelete = async (docId: string) => {
    if (!kbId) return
    try {
      await documentApi.delete(kbId, docId)
      message.success('删除成功')
      fetchDocs()
    } catch { message.error('删除失败') }
  }

  const handleToggleStatus = async (doc: Document) => {
    if (!kbId) return
    try {
      await documentApi.toggleStatus(kbId, doc.id, !doc.is_active)
      message.success('状态已更新')
      fetchDocs()
    } catch { message.error('更新失败') }
  }

  const columns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 80 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => {
        const colors: Record<string, string> = { processing: '#faad14', completed: '#52c41a', error: '#ff4d4f' }
        const labels: Record<string, string> = { processing: '处理中', completed: '已完成', error: '失败' }
        return <span style={{ color: colors[s] || '#999' }}>{labels[s] || s}</span>
      },
    },
    { title: '分块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
    { title: '字符数', dataIndex: 'char_count', key: 'char_count', width: 100 },
    {
      title: '启用', dataIndex: 'is_active', key: 'is_active', width: 80,
      render: (v: boolean, record: Document) => (
        <Switch size="small" checked={v} onChange={() => handleToggleStatus(record)} />
      ),
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作', key: 'actions', width: 100,
      render: (_: unknown, record: Document) => (
        <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  return (
    <Card
      title={kb?.name || '知识库详情'}
      extra={
        <Space>
          <Button onClick={() => navigate(`/knowledge-bases/${kbId}/chat`)}>
            AI 对话
          </Button>
          <Button onClick={() => navigate('/knowledge-bases')}>
            返回列表
          </Button>
        </Space>
      }
    >
      <Tabs
        defaultActiveKey="documents"
        items={[
          {
            key: 'documents',
            label: '文档管理',
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Space>
                  <Upload
                    accept=".pdf,.md,.txt"
                    showUploadList={false}
                    beforeUpload={(file) => { handleUpload(file); return false }}
                  >
                    <Button icon={<UploadOutlined />}>上传文档</Button>
                  </Upload>
                  <Button
                    icon={<PlusOutlined />}
                    onClick={() => setManualModal(true)}
                  >
                    手动录入
                  </Button>
                </Space>
                <Table rowKey="id" columns={columns} dataSource={docs} loading={loading} />

                {/* 手动录入 Modal */}
                {manualModal && (
                  <Card size="small" title="手动录入知识">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Input
                        placeholder="标题"
                        value={manualTitle}
                        onChange={(e) => setManualTitle(e.target.value)}
                      />
                      <Input.TextArea
                        rows={6}
                        placeholder="知识内容"
                        value={manualContent}
                        onChange={(e) => setManualContent(e.target.value)}
                      />
                      <Space>
                        <Button type="primary" onClick={handleManualCreate}>提交</Button>
                        <Button onClick={() => setManualModal(false)}>取消</Button>
                      </Space>
                    </Space>
                  </Card>
                )}
              </Space>
            ),
          },
          {
            key: 'search',
            label: '检索测试',
            children: (
              <Card size="small">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Input.Search
                    placeholder="输入查询文本，测试检索效果..."
                    enterButton={<><SearchOutlined /> 检索</>}
                    onSearch={(value) => message.info(`检索: ${value}（功能开发中）`)}
                  />
                </Space>
              </Card>
            ),
          },
        ]}
      />
    </Card>
  )
}
