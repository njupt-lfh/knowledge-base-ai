import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Button, Table, Space, Upload, message, Tabs, Input, Switch,
  Popconfirm, Drawer, List, Tag, Typography, Modal, Select,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, SearchOutlined,
  InboxOutlined, EyeOutlined, TagsOutlined, MessageOutlined, UnorderedListOutlined, ToolOutlined,
  ApartmentOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import GovernancePanel from '../components/Governance/GovernancePanel'
import ConflictsPanel from '../components/Conflicts/ConflictsPanel'
import { conflictsApi } from '../api/conflicts'
import { knowledgeApi } from '../api/knowledge'
import { documentApi } from '../api/document'
import request from '../api/request'
import HudPanel from '../components/common/HudPanel'
import ColdKnowledgeBadge from '../components/Charts/ColdKnowledgeBadge'
import KnowledgeHealthPanel from '../components/Health/KnowledgeHealthPanel'
import SearchRadarChart from '../components/Charts/SearchRadarChart'
import KnowledgeGraphChart from '../components/Charts/KnowledgeGraphChart'
import FolderSyncPanel from '../components/Sync/FolderSyncPanel'
import { graphApi, type KnowledgeGraphSnapshot } from '../api/graph'
import { statsApi, type ColdKnowledgeStats } from '../api/stats'
import type { KnowledgeBase, Document, Chunk, SearchResultItem } from '../types'
import './KnowledgeDetail.css'

const { Dragger } = Upload

export default function KnowledgeDetail() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [manualModal, setManualModal] = useState(false)
  const [manualTitle, setManualTitle] = useState('')
  const [manualContent, setManualContent] = useState('')
  const [chunksDrawer, setChunksDrawer] = useState(false)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [chunksDocName, setChunksDocName] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([])
  const [searching, setSearching] = useState(false)
  const [tags, setTags] = useState<{ id: string; name: string }[]>([])
  const [docTags, setDocTags] = useState<Record<string, string[]>>({})
  const [tagModal, setTagModal] = useState(false)
  const [tagDocId, setTagDocId] = useState<string | null>(null)
  const [tagDocTags, setTagDocTags] = useState<string[]>([])
  const [newTagName, setNewTagName] = useState('')
  const [tagFilter, setTagFilter] = useState<string | null>(null)
  const [editingChunk, setEditingChunk] = useState<Chunk | null>(null)
  const [editChunkContent, setEditChunkContent] = useState('')
  const [uploadFlash, setUploadFlash] = useState(false)
  const [coldStats, setColdStats] = useState<ColdKnowledgeStats | null>(null)
  const [activeTab, setActiveTab] = useState('documents')
  const [healthTick, setHealthTick] = useState(0)
  const [graphData, setGraphData] = useState<KnowledgeGraphSnapshot | null>(null)
  const [graphLoading, setGraphLoading] = useState(false)

  const fetchGraph = useCallback(async () => {
    if (!kbId) return
    setGraphLoading(true)
    try {
      setGraphData((await graphApi.getSnapshot(kbId)).data)
    } catch {
      message.error('获取知识图谱失败')
    } finally {
      setGraphLoading(false)
    }
  }, [kbId])

  useEffect(() => {
    if (activeTab === 'graph') fetchGraph()
  }, [activeTab, fetchGraph, healthTick])

  const fetchKb = useCallback(async () => {
    if (!kbId) return
    try { setKb((await knowledgeApi.getById(kbId)).data) }
    catch { message.error('获取知识库详情失败') }
  }, [kbId])

  const fetchTags = useCallback(async () => {
    if (!kbId) return
    try { setTags((await request.get(`/api/knowledge-bases/${kbId}/tags`)).data) }
    catch { /* tags not critical */ }
  }, [kbId])

  const fetchDocs = useCallback(async () => {
    if (!kbId) return
    setLoading(true)
    try {
      const res = await documentApi.list(kbId)
      setDocs(res.data.items)
      const ids = res.data.items.map((d: Document) => d.id).join(',')
      if (ids) {
        const tr = await request.get(`/api/knowledge-bases/${kbId}/documents/tag-map?doc_ids=${ids}`)
        setDocTags(tr.data)
      }
    } catch { message.error('获取文档列表失败') }
    setLoading(false)
  }, [kbId])

  const fetchColdStats = useCallback(async () => {
    if (!kbId) return
    try {
      setColdStats((await statsApi.coldKnowledge(kbId)).data)
    } catch { /* optional */ }
  }, [kbId])

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => { fetchKb(); fetchDocs(); fetchTags(); fetchColdStats() }, [fetchKb, fetchDocs, fetchTags, fetchColdStats])
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    const hasProcessing = docs.some((d) => d.status === 'processing')
    if (!hasProcessing) return
    const timer = setInterval(fetchDocs, 3000)
    return () => clearInterval(timer)
  }, [docs, fetchDocs])

  const handleUpload = async (file: File) => {
    if (!kbId) return
    try {
      await documentApi.upload(kbId, file)
      message.success('上传成功')
      setUploadFlash(true)
      setTimeout(() => setUploadFlash(false), 600)
      fetchDocs()
    } catch {
      message.error('上传失败')
    }
  }

  const handleManualCreate = async () => {
    if (!kbId || !manualTitle || !manualContent) return
    try {
      const pre = await conflictsApi.precheck(kbId, manualContent)
      if (pre.data.status === 'duplicate') {
        message.warning(pre.data.message || '内容与已有知识高度相似，仍将提交由门禁过滤')
      } else if (pre.data.status === 'conflict') {
        message.warning(pre.data.message || '可能与已有知识冲突，提交后进入裁决队列')
      }
      await documentApi.createManual(kbId, { title: manualTitle, content: manualContent })
      message.success('录入成功'); setManualModal(false); setManualTitle(''); setManualContent(''); fetchDocs()
    } catch { message.error('录入失败') }
  }

  const handleDelete = async (docId: string) => {
    if (!kbId) return
    try { await documentApi.delete(kbId, docId); message.success('删除成功'); fetchDocs() }
    catch { message.error('删除失败') }
  }

  const handleToggleStatus = async (doc: Document) => {
    if (!kbId) return
    try { await documentApi.toggleStatus(kbId, doc.id, !doc.is_active); message.success('状态已更新'); fetchDocs() }
    catch { message.error('更新失败') }
  }

  const handleBatchToggle = async (isActive: boolean) => {
    if (!kbId || selectedRowKeys.length === 0) return
    try {
      await request.put(`/api/knowledge-bases/${kbId}/documents/batch/status`, {
        doc_ids: selectedRowKeys as string[], is_active: isActive,
      })
      message.success(`已${isActive ? '启用' : '禁用'} ${selectedRowKeys.length} 个文档`)
      setSelectedRowKeys([]); fetchDocs()
    } catch { message.error('批量操作失败') }
  }

  const handleBatchDelete = async () => {
    if (!kbId || selectedRowKeys.length === 0) return
    try {
      await request.delete(`/api/knowledge-bases/${kbId}/documents/batch`, {
        data: { doc_ids: selectedRowKeys as string[] },
      })
      message.success(`已删除 ${selectedRowKeys.length} 个文档`)
      setSelectedRowKeys([]); fetchDocs()
    } catch { message.error('批量删除失败') }
  }

  const showChunks = async (doc: Document) => {
    setChunksDocName(doc.filename); setChunksDrawer(true)
    try { setChunks((await request.get(`/api/documents/${doc.id}/chunks`)).data) }
    catch { message.error('获取知识块失败') }
  }

  const handleChunkToggle = async (chunk: Chunk) => {
    try {
      await request.put(`/api/chunks/${chunk.id}/status?is_active=${!chunk.is_active}`)
      setChunks((prev) => prev.map((c) => (c.id === chunk.id ? { ...c, is_active: !c.is_active } : c)))
    } catch { message.error('切换状态失败') }
  }

  const openTagEditor = async (doc: Document) => {
    setTagDocId(doc.id)
    try {
      const r = await request.get(`/api/knowledge-bases/${kbId}/documents/${doc.id}/tags`)
      setTagDocTags(r.data.map((t: { id: string }) => t.id))
    } catch { setTagDocTags([]) }
    setTagModal(true)
  }

  const saveDocTags = async () => {
    if (!kbId || !tagDocId) return
    try {
      await request.post(`/api/knowledge-bases/${kbId}/documents/${tagDocId}/tags`, { tag_ids: tagDocTags })
      message.success('标签已更新')
      setTagModal(false)
      fetchDocs()
    } catch { message.error('标签更新失败') }
  }

  const createTag = async () => {
    if (!kbId || !newTagName.trim()) return
    try {
      const r = await request.post(`/api/knowledge-bases/${kbId}/tags`, { name: newTagName.trim() })
      setTags((prev) => [...prev, r.data])
      setTagDocTags((prev) => [...prev, r.data.id])
      setNewTagName('')
      message.success('标签已创建')
    } catch { message.error('创建标签失败') }
  }

  const handleSearch = async (query: string) => {
    if (!query.trim() || !kbId) return
    setSearchQuery(query); setSearching(true)
    try {
      const res = await request.post<{ items: SearchResultItem[] }>(
        `/api/knowledge-bases/${kbId}/search`, { query, top_k: 5 },
      )
      setSearchResults(res.data.items)
    } catch { message.error('检索失败') }
    setSearching(false)
  }

  const columns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    {
      title: '标签', key: 'tags', width: 200,
      render: (_: unknown, record: Document) => {
        const names = docTags[record.id] || []
        return names.length > 0
          ? names.map((n) => <Tag key={n} color="blue">{n}</Tag>)
          : <Typography.Text type="secondary">—</Typography.Text>
      },
    },
    { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 80 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => {
        if (s === 'processing') return <span className="status-processing">处理中</span>
        if (s === 'completed') return <span className="status-completed">已完成</span>
        if (s === 'error') return <span className="status-error">失败</span>
        return <span className="status-completed">{s}</span>
      },
    },
    { title: '分块数', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
    {
      title: '门禁',
      key: 'ingest_gate',
      width: 100,
      render: (_: unknown, record: Document) => {
        const dup = record.ingest_duplicate_count || 0
        const conf = record.ingest_conflict_count || 0
        if (!dup && !conf) return <Typography.Text type="secondary">—</Typography.Text>
        return (
          <Space size={4}>
            {dup > 0 && <Tag color="gold">重复 {dup}</Tag>}
            {conf > 0 && <Tag color="red">冲突 {conf}</Tag>}
          </Space>
        )
      },
    },
    {
      title: '启用', dataIndex: 'is_active', key: 'is_active', width: 80,
      render: (v: boolean, record: Document) => (
        <Switch size="small" checked={v} onChange={() => handleToggleStatus(record)} />
      ),
    },
    {
      title: '操作', key: 'actions', width: 220,
      render: (_: unknown, record: Document) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => showChunks(record)}>分块</Button>
          <Button size="small" icon={<TagsOutlined />} onClick={() => openTagEditor(record)}>标签</Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
      <div className="kb-detail__header">
        <div>
          <h2 className="page-title">{kb?.name || '知识库详情'}</h2>
          <p className="page-subtitle">{kb?.description || '文档管理与检索测试'}</p>
        </div>
        <Space wrap align="center">
          {coldStats && (
            <ColdKnowledgeBadge
              data={coldStats}
              compact
              onClick={() => setActiveTab('governance')}
            />
          )}
          <Button type="primary" icon={<MessageOutlined />} onClick={() => navigate(`/knowledge-bases/${kbId}/chat`)}>
            AI 对话
          </Button>
          <Button icon={<UnorderedListOutlined />} onClick={() => navigate(`/knowledge-bases/${kbId}/gaps`)}>
            补全任务
          </Button>
          <Button onClick={() => navigate('/knowledge-bases')}>返回列表</Button>
        </Space>
      </div>

      <HudPanel className="kb-detail__panel">
      {kbId && (
        <KnowledgeHealthPanel
          kbId={kbId}
          refreshToken={healthTick}
          onNavigate={(tab) => {
            if (tab === 'gaps') navigate(`/knowledge-bases/${kbId}/gaps`)
            else setActiveTab(tab)
          }}
        />
      )}
      <Tabs activeKey={activeTab} onChange={setActiveTab} className="kb-detail__tabs" items={[
        {
          key: 'documents',
          label: '文档管理',
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Space wrap>
                <Dragger
                  accept=".pdf,.md,.txt,.png,.jpg,.jpeg,.webp,.gif"
                  showUploadList={false}
                  className={`upload-dragger${uploadFlash ? ' upload-dragger--flash' : ''}`}
                  beforeUpload={(file) => { handleUpload(file); return false }}
                  style={{ width: 300, padding: 12 }}
                >
                  <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                  <p className="ant-upload-text">拖拽文件或点击上传</p>
                  <p className="ant-upload-hint">PDF / Markdown / TXT / 图片（PNG、JPG、WEBP）</p>
                </Dragger>
                <Button icon={<PlusOutlined />} onClick={() => setManualModal(true)}>手动录入</Button>
                <Select
                  allowClear
                  placeholder="按标签筛选"
                  style={{ width: 160 }}
                  value={tagFilter}
                  onChange={(v) => setTagFilter(v || null)}
                  options={tags.map((t) => ({ value: t.name, label: t.name }))}
                />
                {selectedRowKeys.length > 0 && (
                  <Space>
                    <Button size="small" onClick={() => handleBatchToggle(true)}>批量启用</Button>
                    <Button size="small" onClick={() => handleBatchToggle(false)}>批量禁用</Button>
                    <Popconfirm title={`确定删除 ${selectedRowKeys.length} 个文档?`} onConfirm={handleBatchDelete}>
                      <Button size="small" danger>批量删除</Button>
                    </Popconfirm>
                    <Typography.Text type="secondary">已选 {selectedRowKeys.length} 项</Typography.Text>
                  </Space>
                )}
              </Space>
              <Table
                rowKey="id"
                columns={columns}
                loading={loading}
                rowClassName={(record) => (record.status === 'processing' ? 'doc-row-processing' : '')}
                rowSelection={{
                  selectedRowKeys,
                  onChange: (keys) => setSelectedRowKeys(keys),
                }}
                dataSource={tagFilter ? docs.filter((d) => (docTags[d.id] || []).includes(tagFilter)) : docs}
              />

              <Modal title="手动录入知识" open={manualModal} onCancel={() => setManualModal(false)} onOk={handleManualCreate} okText="提交" cancelText="取消">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Input placeholder="标题" value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} />
                  <Input.TextArea rows={8} placeholder="知识内容" value={manualContent} onChange={(e) => setManualContent(e.target.value)} />
                </Space>
              </Modal>

              <Modal title="编辑标签" open={tagModal} onCancel={() => setTagModal(false)} onOk={saveDocTags} okText="保存">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Select
                    mode="multiple"
                    style={{ width: '100%' }}
                    placeholder="选择标签"
                    value={tagDocTags}
                    onChange={(v) => setTagDocTags(v)}
                    options={tags.map((t) => ({ value: t.id, label: t.name }))}
                  />
                  <Space.Compact style={{ width: '100%' }}>
                    <Input placeholder="新建标签" value={newTagName} onChange={(e) => setNewTagName(e.target.value)} onPressEnter={createTag} />
                    <Button onClick={createTag}>添加</Button>
                  </Space.Compact>
                </Space>
              </Modal>

              <Drawer title={`知识块: ${chunksDocName}`} open={chunksDrawer} onClose={() => setChunksDrawer(false)} width={700}>
                <List dataSource={chunks} renderItem={(chunk) => (
                  <List.Item actions={[
                    <Switch size="small" checked={chunk.is_active} onChange={() => handleChunkToggle(chunk)} />,
                    <Button size="small" onClick={() => { setEditingChunk(chunk); setEditChunkContent(chunk.content) }}>编辑</Button>,
                  ]}>
                    <List.Item.Meta
                      title={<Space><Tag color="blue">#{chunk.chunk_index}</Tag><Typography.Text type="secondary">{chunk.char_count} 字符 | 命中 {chunk.hit_count} 次</Typography.Text></Space>}
                      description={
                        editingChunk?.id === chunk.id ? (
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <Input.TextArea rows={4} value={editChunkContent} onChange={(e) => setEditChunkContent(e.target.value)} />
                            <Space>
                              <Button size="small" type="primary" onClick={async () => {
                                await request.put(`/api/chunks/${chunk.id}`, { content: editChunkContent })
                                setChunks((prev) => prev.map((c) => c.id === chunk.id ? { ...c, content: editChunkContent, char_count: editChunkContent.length } : c))
                                setEditingChunk(null); message.success('已更新')
                              }}>保存</Button>
                              <Button size="small" onClick={() => setEditingChunk(null)}>取消</Button>
                            </Space>
                          </Space>
                        ) : (
                          <Typography.Paragraph ellipsis={{ rows: 3, expandable: true, symbol: '展开' }} style={{ whiteSpace: 'pre-wrap' }}>{chunk.content}</Typography.Paragraph>
                        )
                      }
                    />
                  </List.Item>
                )} />
              </Drawer>
            </Space>
          ),
        },
        {
          key: 'conflicts',
          label: '入库冲突',
          children: kbId ? <ConflictsPanel kbId={kbId} /> : null,
        },
        {
          key: 'governance',
          label: '治理建议',
          children: kbId ? (
            <GovernancePanel kbId={kbId} onApplied={() => { fetchColdStats(); setHealthTick((t) => t + 1) }} />
          ) : null,
        },
        {
          key: 'graph',
          label: <><ApartmentOutlined /> 知识图谱</>,
          children: kbId ? (
            graphLoading ? (
              <Typography.Text type="secondary">加载图谱中…</Typography.Text>
            ) : (
              <KnowledgeGraphChart
                nodes={graphData?.nodes ?? []}
                edges={graphData?.edges ?? []}
                relationCount={graphData?.relation_count ?? 0}
              />
            )
          ) : null,
        },
        {
          key: 'sync',
          label: <><SyncOutlined /> 文件夹同步</>,
          children: kbId ? (
            <FolderSyncPanel
              kbId={kbId}
              onSynced={() => {
                fetchDocs()
                setHealthTick((t) => t + 1)
              }}
            />
          ) : null,
        },
        {
          key: 'search',
          label: '检索测试',
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Input.Search placeholder="输入查询文本..." enterButton={<><SearchOutlined /> 检索</>} onSearch={handleSearch} loading={searching} size="large" />
              {searchResults.length > 0 && (
                <SearchRadarChart
                  scores={searchResults.map((r) => Number(r.score))}
                  query={searchQuery}
                />
              )}
              {searchResults.length > 0 && (
                <div>
                  {searchResults.map((item, i) => (
                    <motion.div
                      key={item.chunk_id}
                      className="search-result-item animate-fade-in-up"
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.08, duration: 0.35 }}
                    >
                      <Space style={{ marginBottom: 8 }}>
                        <Tag color="cyan" className="search-result-score">相似度: {item.score}</Tag>
                        <Tag>块 #{item.chunk_index}</Tag>
                      </Space>
                      <Typography.Paragraph
                        ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                        style={{ whiteSpace: 'pre-wrap', margin: 0, color: 'var(--text-secondary)' }}
                      >
                        {item.content}
                      </Typography.Paragraph>
                    </motion.div>
                  ))}
                </div>
              )}
              {searchResults.length === 0 && searchQuery && !searching && (
                <Typography.Text type="secondary">未找到匹配的知识内容</Typography.Text>
              )}
            </Space>
          ),
        },
      ]} />
      </HudPanel>
    </>
  )
}
