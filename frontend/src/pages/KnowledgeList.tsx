import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Button, Table, Space, Modal, Form, Input, InputNumber, message, Popconfirm } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons'
import { knowledgeApi } from '../api/knowledge'
import type { KnowledgeBase } from '../types'

export default function KnowledgeList() {
  const navigate = useNavigate()
  const [data, setData] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null)
  const [form] = Form.useForm()

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await knowledgeApi.list()
      setData(res.data.items)
    } catch {
      message.error('获取知识库列表失败')
    }
    setLoading(false)
  }

  useEffect(() => { fetchData() }, [])

  const handleCreate = async (values: Record<string, unknown>) => {
    try {
      await knowledgeApi.create(values as { name: string })
      message.success('创建成功')
      setModalOpen(false)
      form.resetFields()
      fetchData()
    } catch {
      message.error('创建失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await knowledgeApi.delete(id)
      message.success('删除成功')
      fetchData()
    } catch {
      message.error('删除失败')
    }
  }

  const handleEdit = async (values: Record<string, unknown>) => {
    if (!editingKb) return
    try {
      await knowledgeApi.update(editingKb.id, values as Partial<KnowledgeBase>)
      message.success('更新成功')
      setModalOpen(false)
      setEditingKb(null)
      form.resetFields()
      fetchData()
    } catch {
      message.error('更新失败')
    }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '文档数', dataIndex: 'document_count', key: 'document_count', width: 100 },
    { title: '分块大小', dataIndex: 'chunk_size', key: 'chunk_size', width: 100 },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: KnowledgeBase) => (
        <Space>
          <Button size="small" onClick={() => navigate(`/knowledge-bases/${record.id}`)}>
            查看
          </Button>
          <Button size="small" onClick={() => navigate(`/knowledge-bases/${record.id}/chat`)}>
            对话
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingKb(record)
              form.setFieldsValue(record)
              setModalOpen(true)
            }}
          />
          <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="知识库列表"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditingKb(null)
          form.resetFields()
          setModalOpen(true)
        }}>
          新建知识库
        </Button>
      }
    >
      <Table rowKey="id" columns={columns} dataSource={data} loading={loading} />

      <Modal
        title={editingKb ? '编辑知识库' : '新建知识库'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingKb(null); form.resetFields() }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={editingKb ? handleEdit : handleCreate}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：技术文档库" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="知识库描述（可选）" />
          </Form.Item>
          <Form.Item name="chunk_size" label="分块大小" initialValue={500}>
            <InputNumber min={100} max={2000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="chunk_overlap" label="分块重叠" initialValue={50}>
            <InputNumber min={0} max={500} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
