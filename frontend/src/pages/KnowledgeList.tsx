/**
 * 知识库列表页
 * 卡片网格展示、搜索、新建/编辑/删除知识库
 * 主要导出：默认 KnowledgeList 页面组件
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Modal, Form, InputNumber, message, Spin } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { knowledgeApi } from '../api/knowledge'
import type { KnowledgeBase } from '../types'
import KnowledgeCardGrid from '../components/KnowledgeCard/KnowledgeCardGrid'

/** 知识库管理首页 */
export default function KnowledgeList() {
  const navigate = useNavigate()
  const [data, setData] = useState<KnowledgeBase[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null)
  const [form] = Form.useForm()
  const [searchText, setSearchText] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const pageSize = 100
      let page = 1
      let items: KnowledgeBase[] = []
      let count = 0
      // 分页拉取直至拿全量（page_size=100）
      do {
        const res = await knowledgeApi.list({
          page,
          page_size: pageSize,
          search: searchText || undefined,
        })
        items = [...items, ...res.data.items]
        count = res.data.total
        page += 1
      } while (items.length < count)
      setData(items)
      setTotal(count)
    } catch {
      message.error('获取知识库列表失败')
    }
    setLoading(false)
  }, [searchText])

  /* eslint-disable react-hooks/set-state-in-effect -- searchText 变化时重新拉列表 */
  useEffect(() => {
    fetchData()
  }, [fetchData])
  /* eslint-enable react-hooks/set-state-in-effect */

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

  const openCreate = () => {
    setEditingKb(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (kb: KnowledgeBase) => {
    setEditingKb(kb)
    form.setFieldsValue(kb)
    setModalOpen(true)
  }

  return (
    <Spin spinning={loading && data.length > 0}>
      <div className="kb-list-header">
        <div>
          <h2 className="page-title">知识库管理</h2>
          <p className="page-subtitle">
            管理您的智能知识库资产
            {total > 0 ? ` · 共 ${total} 个` : ''}
          </p>
        </div>
        <Input.Search
          className="kb-list-search"
          placeholder="搜索知识库..."
          allowClear
          onSearch={(v) => setSearchText(v)}
          prefix={<SearchOutlined style={{ color: 'var(--text-muted)' }} />}
        />
      </div>

      <KnowledgeCardGrid
        data={data}
        loading={loading}
        onCreate={openCreate}
        onView={(id) => navigate(`/knowledge-bases/${id}`)}
        onChat={(id) => navigate(`/knowledge-bases/${id}/chat`)}
        onEdit={openEdit}
        onDelete={handleDelete}
      />

      <Modal
        title={editingKb ? '编辑知识库' : '新建知识库'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false)
          setEditingKb(null)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        okText="确认"
        cancelText="取消"
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
    </Spin>
  )
}
