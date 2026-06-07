/**
 * 知识库详情页
 * 文档管理、冲突/治理/图谱/同步/检索测试等多 Tab
 * 主要导出：默认 KnowledgeDetail 页面组件
 */
import { useEffect, useState, useCallback, useRef } from 'react'

import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Button,
  Table,
  Space,
  Upload,
  message,
  Input,
  Switch,
  Popconfirm,
  Drawer,
  List,
  Tag,
  Typography,
  Modal,
  Select,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  SearchOutlined,
  InboxOutlined,
  EyeOutlined,
  TagsOutlined,
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

/** 单知识库文档、治理、图谱与检索测试工作台 */
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
  const [focusChunkId, setFocusChunkId] = useState<string | null>(null)
  const chunksListRef = useRef<HTMLDivElement>(null)
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
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') || 'documents'

  // 侧栏切换时更新 URL param
  const handleTabChange = (tab: string) => {
    setSearchParams({ tab })
  }
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
    try {
      setKb((await knowledgeApi.getById(kbId)).data)
    } catch {
      message.error('获取知识库详情失败')
    }
  }, [kbId])

  const fetchTags = useCallback(async () => {
    if (!kbId) return
    try {
      setTags((await request.get(`/api/knowledge-bases/${kbId}/tags`)).data)
    } catch {
      /* 标签加载失败非阻塞 */
    }
  }, [kbId])

  const fetchDocs = useCallback(async () => {
    if (!kbId) return
    setLoading(true)
    try {
      const res = await documentApi.list(kbId)
      setDocs(res.data.items)
      const ids = res.data.items.map((d: Document) => d.id).join(',')
      if (ids) {
        const tr = await request.get(
          `/api/knowledge-bases/${kbId}/documents/tag-map?doc_ids=${ids}`,
        )
        setDocTags(tr.data)
      }
    } catch {
      message.error('获取文档列表失败')
    }
    setLoading(false)
  }, [kbId])

  const fetchColdStats = useCallback(async () => {
    if (!kbId) return
    try {
      setColdStats((await statsApi.coldKnowledge(kbId)).data)
    } catch {
      /* 冷知识统计可选 */
    }
  }, [kbId])

  /* eslint-disable react-hooks/set-state-in-effect -- kbId 变化时并行加载详情数据 */
  useEffect(() => {
    fetchKb()
    fetchDocs()
    fetchTags()
    fetchColdStats()
  }, [fetchKb, fetchDocs, fetchTags, fetchColdStats])
  /* eslint-enable react-hooks/set-state-in-effect */

  // 存在 processing 文档时每 3 秒轮询刷新状态
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
      message.success('文件已上传，正在后台入库（小文件约 10–30 秒，PDF 约 1–3 分钟）')
      setUploadFlash(true)
      setTimeout(() => setUploadFlash(false), 600)
      fetchDocs()
    } catch {
      message.error('上传失败')
    }
  }

  /** 手动录入：先预检去重/冲突，再提交入库门禁 */
  const handleManualCreate = async () => {
    if (!kbId || !manualTitle || !manualContent) return
    try {
      // 入库前预检：向量相似度兜底 + 语义重复/冲突判断
      const pre = await conflictsApi.precheck(kbId, manualContent)
      if (pre.data.status === 'duplicate') {
        message.warning(pre.data.message || '内容与已有知识高度相似，仍将提交由门禁过滤')
      } else if (pre.data.status === 'conflict') {
        message.warning(pre.data.message || '可能与已有知识冲突，提交后进入裁决队列')
      }
      await documentApi.createManual(kbId, { title: manualTitle, content: manualContent })
      message.success('录入成功')
      setManualModal(false)
      setManualTitle('')
      setManualContent('')
      fetchDocs()
    } catch {
      message.error('录入失败')
    }
  }

  const handleDelete = async (docId: string) => {
    if (!kbId) return
    try {
      await documentApi.delete(kbId, docId)
      message.success('删除成功')
      fetchDocs()
    } catch {
      message.error('删除失败')
    }
  }

  const handleToggleStatus = async (doc: Document) => {
    if (!kbId) return
    try {
      await documentApi.toggleStatus(kbId, doc.id, !doc.is_active)
      message.success('状态已更新')
      fetchDocs()
    } catch {
      message.error('更新失败')
    }
  }

  const handleReindex = async (doc: Document) => {
    if (!kbId) return
    try {
      await documentApi.reindex(kbId, doc.id)
      message.success('已重新入库，请稍候刷新')
      fetchDocs()
    } catch {
      message.error('重新入库失败')
    }
  }

  /** 批量启用/禁用：前端传 doc_ids 数组，后端遍历同步 Chroma */
  const handleBatchToggle = async (isActive: boolean) => {
    if (!kbId || selectedRowKeys.length === 0) return
    try {
      await request.put(`/api/knowledge-bases/${kbId}/documents/batch/status`, {
        doc_ids: selectedRowKeys as string[],
        is_active: isActive,
      })
      message.success(`已${isActive ? '启用' : '禁用'} ${selectedRowKeys.length} 个文档`)
      setSelectedRowKeys([])
      fetchDocs()
    } catch {
      message.error('批量操作失败')
    }
  }

  /** 批量删除：后端级联清理 Chroma 向量 + 上传文件 */
  const handleBatchDelete = async () => {
    if (!kbId || selectedRowKeys.length === 0) return
    try {
      await request.delete(`/api/knowledge-bases/${kbId}/documents/batch`, {
        data: { doc_ids: selectedRowKeys as string[] },
      })
      message.success(`已删除 ${selectedRowKeys.length} 个文档`)
      setSelectedRowKeys([])
      fetchDocs()
    } catch {
      message.error('批量删除失败')
    }
  }

  const showChunks = async (doc: Document, highlightChunkId?: string) => {
    setChunksDocName(doc.filename)
    setFocusChunkId(highlightChunkId ?? null)
    setChunksDrawer(true)
    try {
      setChunks((await request.get(`/api/documents/${doc.id}/chunks`)).data)
    } catch {
      message.error('获取知识块失败')
    }
  }

  const locateGovernanceChunk = async (documentId: string, chunkId?: string) => {
    let doc = docs.find((d) => d.id === documentId)
    if (!doc && kbId) {
      try {
        doc = (await documentApi.getById(kbId, documentId)).data
      } catch {
        message.warning('未找到来源文档，可能已被删除')
        return
      }
    }
    if (!doc) {
      message.warning('未找到来源文档，可能已被删除')
      return
    }
    await showChunks(doc, chunkId)
  }

  useEffect(() => {
    if (!chunksDrawer || !focusChunkId || chunks.length === 0) return
    const timer = window.setTimeout(() => {
      const el = chunksListRef.current?.querySelector(`[data-chunk-id="${focusChunkId}"]`)
      el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }, 150)
    return () => window.clearTimeout(timer)
  }, [chunksDrawer, focusChunkId, chunks])

  const handleChunkToggle = async (chunk: Chunk) => {
    try {
      await request.put(`/api/chunks/${chunk.id}/status?is_active=${!chunk.is_active}`)
      setChunks((prev) =>
        prev.map((c) => (c.id === chunk.id ? { ...c, is_active: !c.is_active } : c)),
      )
    } catch {
      message.error('切换状态失败')
    }
  }

  const openTagEditor = async (doc: Document) => {
    setTagDocId(doc.id)
    try {
      const r = await request.get(`/api/knowledge-bases/${kbId}/documents/${doc.id}/tags`)
      setTagDocTags(r.data.map((t: { id: string }) => t.id))
    } catch {
      setTagDocTags([])
    }
    setTagModal(true)
  }

  const saveDocTags = async () => {
    if (!kbId || !tagDocId) return
    try {
      await request.post(`/api/knowledge-bases/${kbId}/documents/${tagDocId}/tags`, {
        tag_ids: tagDocTags,
      })
      message.success('标签已更新')
      setTagModal(false)
      fetchDocs()
    } catch {
      message.error('标签更新失败')
    }
  }

  const createTag = async () => {
    if (!kbId || !newTagName.trim()) return
    try {
      const r = await request.post(`/api/knowledge-bases/${kbId}/tags`, { name: newTagName.trim() })
      setTags((prev) => [...prev, r.data])
      setTagDocTags((prev) => [...prev, r.data.id])
      setNewTagName('')
      message.success('标签已创建')
    } catch {
      message.error('创建标签失败')
    }
  }

  /** 检索测试：调用 Hybrid 检索 API，结果用于雷达图展示相似度 */
  const handleSearch = async (query: string) => {
    if (!query.trim() || !kbId) return
    setSearchQuery(query)
    setSearching(true)
    setSearchResults([])
    try {
      const res = await request.post<{ items: SearchResultItem[] }>(
        `/api/knowledge-bases/${kbId}/search`,
        { query, top_k: 5 },
        { timeout: 90000 },
      )
      setSearchResults(res.data?.items ?? [])
    } catch {
      setSearchResults([])
      message.error('检索失败，请确认后端已重启且 Embedding 服务可用')
    }
    setSearching(false)
  }

  const columns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    {
      title: '标签',
      key: 'tags',
      width: 200,
      render: (_: unknown, record: Document) => {
        const names = docTags[record.id] || []
        return names.length > 0 ? (
          names.map((n) => (
            <Tag key={n} color="blue">
              {n}
            </Tag>
          ))
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        )
      },
    },
    { title: '类型', dataIndex: 'file_type', key: 'file_type', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
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
      title: '启用',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean, record: Document) => (
        <Switch size="small" checked={v} onChange={() => handleToggleStatus(record)} />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_: unknown, record: Document) => (
        <Space wrap>
          {(record.status === 'processing' || record.status === 'error') && (
            <Button size="small" type="primary" onClick={() => handleReindex(record)}>
              重新入库
            </Button>
          )}
          <Button size="small" icon={<EyeOutlined />} onClick={() => showChunks(record)}>
            分块
          </Button>
          <Button size="small" icon={<TagsOutlined />} onClick={() => openTagEditor(record)}>
            标签
          </Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div
      className={`kb-detail${activeTab === 'graph' ? ' kb-detail--graph' : ''}${activeTab === 'governance' ? ' kb-detail--governance' : ''}`}
    >
      <div className="kb-detail__header">
        <h2
          className="page-title kb-detail__headline"
          title={`${kb?.name || '知识库详情'}（${kb?.description?.trim() || '文档管理与检索测试'}）`}
        >
          <span className="kb-detail__name">{kb?.name || '知识库详情'}</span>
          <span className="kb-detail__desc">
            （{kb?.description?.trim() || '文档管理与检索测试'}）
          </span>
        </h2>
        {coldStats && (
          <ColdKnowledgeBadge
            data={coldStats}
            compact
            onClick={() => handleTabChange('governance')}
          />
        )}
      </div>

      <HudPanel className="kb-detail__panel">
        {kbId && activeTab !== 'graph' && (
          <KnowledgeHealthPanel
            kbId={kbId}
            refreshToken={healthTick}
            onNavigate={(tab) => {
              if (tab === 'gaps') navigate(`/knowledge-bases/${kbId}/gaps`)
              else handleTabChange(tab)
            }}
          />
        )}
        <div
          className={`kb-detail__tab-content${activeTab === 'graph' ? ' kb-detail__tab-content--graph' : ''}`}
        >
          {activeTab === 'documents' && (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Space wrap>
                <Dragger
                  accept=".pdf,.md,.txt,.png,.jpg,.jpeg,.webp,.gif"
                  showUploadList={false}
                  className={`upload-dragger${uploadFlash ? ' upload-dragger--flash' : ''}`}
                  beforeUpload={(file) => {
                    handleUpload(file)
                    return false
                  }}
                  style={{ width: 300, padding: 12 }}
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text">拖拽文件或点击上传</p>
                  <p className="ant-upload-hint">PDF / Markdown / TXT / 图片（PNG、JPG、WEBP）</p>
                </Dragger>
                <Button icon={<PlusOutlined />} onClick={() => setManualModal(true)}>
                  手动录入
                </Button>
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
                    <Button size="small" onClick={() => handleBatchToggle(true)}>
                      批量启用
                    </Button>
                    <Button size="small" onClick={() => handleBatchToggle(false)}>
                      批量禁用
                    </Button>
                    <Popconfirm
                      title={`确定删除 ${selectedRowKeys.length} 个文档?`}
                      onConfirm={handleBatchDelete}
                    >
                      <Button size="small" danger>
                        批量删除
                      </Button>
                    </Popconfirm>
                    <Typography.Text type="secondary">
                      已选 {selectedRowKeys.length} 项
                    </Typography.Text>
                  </Space>
                )}
              </Space>
              <Table
                rowKey="id"
                columns={columns}
                loading={loading}
                rowClassName={(record) =>
                  record.status === 'processing' ? 'doc-row-processing' : ''
                }
                rowSelection={{
                  selectedRowKeys,
                  onChange: (keys) => setSelectedRowKeys(keys),
                }}
                dataSource={
                  tagFilter ? docs.filter((d) => (docTags[d.id] || []).includes(tagFilter)) : docs
                }
              />

              <Modal
                title="手动录入知识"
                open={manualModal}
                onCancel={() => setManualModal(false)}
                onOk={handleManualCreate}
                okText="提交"
                cancelText="取消"
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Input
                    placeholder="标题"
                    value={manualTitle}
                    onChange={(e) => setManualTitle(e.target.value)}
                  />
                  <Input.TextArea
                    rows={8}
                    placeholder="知识内容"
                    value={manualContent}
                    onChange={(e) => setManualContent(e.target.value)}
                  />
                </Space>
              </Modal>

              <Modal
                title="编辑标签"
                open={tagModal}
                onCancel={() => setTagModal(false)}
                onOk={saveDocTags}
                okText="保存"
              >
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
                    <Input
                      placeholder="新建标签"
                      value={newTagName}
                      onChange={(e) => setNewTagName(e.target.value)}
                      onPressEnter={createTag}
                    />
                    <Button onClick={createTag}>添加</Button>
                  </Space.Compact>
                </Space>
              </Modal>
            </Space>
          )}
          {activeTab === 'conflicts' && kbId && (
            <ConflictsPanel kbId={kbId} onLocateChunk={locateGovernanceChunk} />
          )}
          {activeTab === 'governance' && kbId && (
            <GovernancePanel
              kbId={kbId}
              onLocateChunk={locateGovernanceChunk}
              onApplied={() => {
                fetchColdStats()
                setHealthTick((t) => t + 1)
              }}
            />
          )}
          {activeTab === 'graph' && (
            <div className="kb-detail__graph-wrap">
              {graphLoading ? (
                <Typography.Text type="secondary">加载图谱中…</Typography.Text>
              ) : (
                <KnowledgeGraphChart
                  nodes={graphData?.nodes ?? []}
                  edges={graphData?.edges ?? []}
                  relationCount={graphData?.relation_count ?? 0}
                />
              )}
            </div>
          )}
          {activeTab === 'sync' && kbId && (
            <FolderSyncPanel
              kbId={kbId}
              onSynced={() => {
                fetchDocs()
                setHealthTick((t) => t + 1)
              }}
            />
          )}
          {activeTab === 'search' && (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Input.Search
                placeholder="输入查询文本..."
                enterButton={
                  <>
                    <SearchOutlined /> 检索
                  </>
                }
                onSearch={handleSearch}
                loading={searching}
                size="large"
              />
              {activeTab === 'search' && searchResults.length > 0 && (
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
                        <Tag color="cyan" className="search-result-score">
                          相似度: {item.score}
                        </Tag>
                        <Tag>块 #{item.chunk_index}</Tag>
                      </Space>
                      <Typography.Paragraph
                        ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                        style={{
                          whiteSpace: 'pre-wrap',
                          margin: 0,
                          color: 'var(--text-secondary)',
                        }}
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
          )}
        </div>
      </HudPanel>

      <Drawer
        title={`知识块: ${chunksDocName}`}
        open={chunksDrawer}
        onClose={() => {
          setChunksDrawer(false)
          setFocusChunkId(null)
          setEditingChunk(null)
        }}
        width={700}
      >
        <div ref={chunksListRef}>
          <List
            dataSource={chunks}
            renderItem={(chunk) => (
              <List.Item
                data-chunk-id={chunk.id}
                className={focusChunkId === chunk.id ? 'kb-chunk-item--focus' : undefined}
                actions={[
                  <Switch
                    size="small"
                    checked={chunk.is_active}
                    onChange={() => handleChunkToggle(chunk)}
                  />,
                  <Button
                    size="small"
                    onClick={() => {
                      setEditingChunk(chunk)
                      setEditChunkContent(chunk.content)
                    }}
                  >
                    编辑
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color="blue">#{chunk.chunk_index}</Tag>
                      <Typography.Text type="secondary">
                        {chunk.char_count} 字符 | 命中 {chunk.hit_count} 次
                      </Typography.Text>
                    </Space>
                  }
                  description={
                    editingChunk?.id === chunk.id ? (
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Input.TextArea
                          rows={4}
                          value={editChunkContent}
                          onChange={(e) => setEditChunkContent(e.target.value)}
                        />
                        <Space>
                          <Button
                            size="small"
                            type="primary"
                            onClick={async () => {
                              await request.put(`/api/chunks/${chunk.id}`, {
                                content: editChunkContent,
                              })
                              setChunks((prev) =>
                                prev.map((c) =>
                                  c.id === chunk.id
                                    ? {
                                        ...c,
                                        content: editChunkContent,
                                        char_count: editChunkContent.length,
                                      }
                                    : c,
                                ),
                              )
                              setEditingChunk(null)
                              message.success('已更新')
                            }}
                          >
                            保存
                          </Button>
                          <Button size="small" onClick={() => setEditingChunk(null)}>
                            取消
                          </Button>
                        </Space>
                      </Space>
                    ) : (
                      <Typography.Paragraph
                        ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                        style={{ whiteSpace: 'pre-wrap' }}
                      >
                        {chunk.content}
                      </Typography.Paragraph>
                    )
                  }
                />
              </List.Item>
            )}
          />
        </div>
      </Drawer>
    </div>
  )
}
