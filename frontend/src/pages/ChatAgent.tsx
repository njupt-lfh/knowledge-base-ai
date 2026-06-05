/**
 * AI 专家对话页
 * 管理会话历史、SSE 流式问答、知识提炼与分享
 * 主要导出：默认 ChatAgent 页面组件
 */
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Space, Typography, message, Modal, Popconfirm, Switch, Tooltip } from 'antd'
import {
  ArrowLeftOutlined,
  ShareAltOutlined,
  BulbOutlined,
  PlusOutlined,
  HistoryOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { chatApi } from '../api/chat'
import { gapApi } from '../api/gap'
import request from '../api/request'
import HudPanel from '../components/common/HudPanel'
import ChatWindow from '../components/Chat/ChatWindow'
import type { ChatMessageData } from '../components/Chat/MessageBubble'
import type { Conversation, Message } from '../types'
import { loadChatFastMode, saveChatFastMode } from '../utils/chatFastMode'
import '../components/Chat/Chat.css'

const CONV_LIST_PAGE_SIZE = 50

/** 知识库下的 RAG 对话主界面 */
export default function ChatAgent() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<ChatMessageData[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [convList, setConvList] = useState<Conversation[]>([])
  const [convHasMore, setConvHasMore] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [initialized, setInitialized] = useState(false)
  const [fastMode, setFastMode] = useState(() => loadChatFastMode(kbId))

  const loadConvList = useCallback(async () => {
    if (!kbId) return []
    try {
      const list = (await chatApi.listConversations(kbId, CONV_LIST_PAGE_SIZE, 0)).data
      setConvList(list)
      setConvHasMore(list.length >= CONV_LIST_PAGE_SIZE)
      return list
    } catch {
      return []
    }
  }, [kbId])

  const loadMessages = useCallback(async (conv: Conversation) => {
    try {
      const msgs = (await chatApi.getMessages(conv.id)).data
      setMessages(
        msgs.map((m: Message) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          sources: m.sources ?? undefined,
        })),
      )
    } catch {
      message.error('加载消息失败')
    }
  }, [])

  const switchConversation = useCallback(
    async (conv: Conversation) => {
      setConversation(conv)
      setShowHistory(false)
      await loadMessages(conv)
    },
    [loadMessages],
  )

  const handleNewChat = async () => {
    if (!kbId) return
    try {
      const res = await chatApi.createConversation(kbId)
      setConversation(res.data)
      setMessages([])
      setShowHistory(false)
      await loadConvList()
      message.success('已创建新对话')
    } catch {
      message.error('创建对话失败')
    }
  }

  useEffect(() => {
    setFastMode(loadChatFastMode(kbId))
  }, [kbId])

  /* eslint-disable react-hooks/set-state-in-effect -- 初始化时加载最近会话并选中 */
  useEffect(() => {
    if (!kbId) return
    loadConvList().then((list) => {
      if (list.length > 0) {
        const latest = [...list].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        )[0]
        switchConversation(latest)
      } else {
        setConversation(null)
        setMessages([])
      }
      setInitialized(true)
    })
  }, [kbId, loadConvList, switchConversation])
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleSend = async () => {
    if (sending || !input.trim()) return

    let conv = conversation
    if (!conv && kbId) {
      try {
        const res = await chatApi.createConversation(kbId)
        conv = res.data
        setConversation(conv)
        await loadConvList()
      } catch {
        message.error('创建对话失败')
        return
      }
    }
    if (!conv) return

    const userMsg: ChatMessageData = { role: 'user', content: input }
    const assistantMsg: ChatMessageData = { role: 'assistant', content: '', isStreaming: true }
    const query = input

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    setSending(true)

    try {
      // SSE 流：逐 event 消费，text 增量拼接、agent_meta/sources/done 即时更新助手气泡
      for await (const event of chatApi.sendMessage(conv.id, query, fastMode)) {
        if (event.type === 'text') {
          // 逐 token 增量：追加到助手消息末尾
          setMessages((prev) =>
            prev.map((msg, i) =>
              i === prev.length - 1 && msg.role === 'assistant'
                ? { ...msg, content: msg.content + event.content }
                : msg,
            ),
          )
        } else if (event.type === 'agent_meta') {
          // Agent 元信息：路由类型、CRAG 评分、图谱/SIM-RAG 使用标记
          setMessages((prev) =>
            prev.map((msg, i) =>
              i === prev.length - 1 && msg.role === 'assistant'
                ? {
                    ...msg,
                    agentMeta: {
                      route: event.route,
                      rounds: event.rounds,
                      sim_rag_used: event.sim_rag_used,
                      sim_sub_queries: event.sim_sub_queries,
                      sim_coverage: event.sim_coverage,
                      crag_score: event.crag_score,
                      graph_used: event.graph_used,
                      refused: event.refused,
                      fast_mode: event.fast_mode,
                    },
                  }
                : msg,
            ),
          )
        } else if (event.type === 'sources') {
          // 检索来源列表：chunk 引用 + 相似度分数
          setMessages((prev) =>
            prev.map((msg, i) =>
              i === prev.length - 1 && msg.role === 'assistant'
                ? { ...msg, sources: event.sources }
                : msg,
            ),
          )
        } else if (event.type === 'done') {
          // 流结束：清除闪烁光标动画，标记 isStreaming=false
          setMessages((prev) =>
            prev.map((msg, i) =>
              i === prev.length - 1 && msg.role === 'assistant'
                ? { ...msg, isStreaming: false }
                : msg,
            ),
          )
        }
      }
    } catch {
      message.error('发送失败')
    }
    setSending(false)
    if (conv) {
      await loadMessages(conv)
      await loadConvList()
    }
  }

  const handleFeedback = (messageId: string, type: 'like' | 'dislike' | 'correction') => {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback: type } : m)))
  }

  const [extractModal, setExtractModal] = useState(false)
  const [extractData, setExtractData] = useState<{
    title: string
    content: string | null
    kb_id: string
    gap_id?: string
    gap_type?: string
    manual_required?: boolean
    source_ref?: string
  } | null>(null)
  const [extracting, setExtracting] = useState(false)

  const handleExtract = async () => {
    if (!conversation) {
      message.info('请先开始一段对话')
      return
    }
    setExtracting(true)
    try {
      const res = await request.post(`/api/conversations/${conversation.id}/extract-knowledge`)
      if (res.data.has_knowledge) {
        setExtractData(res.data)
        setExtractModal(true)
      } else {
        message.info('当前对话未检测到新知识点')
      }
    } catch {
      message.error('知识提炼失败')
    }
    setExtracting(false)
  }

  const confirmExtract = async () => {
    if (!extractData?.gap_id || !extractData.kb_id) return
    try {
      if (extractData.manual_required) {
        message.warning('该缺口需到「补全任务」中人工填写内容后入库')
        navigate(`/knowledge-bases/${extractData.kb_id}/gaps`)
        return
      }
      await gapApi.ingest(extractData.kb_id, extractData.gap_id)
      message.success('知识已通过门禁入库！')
      setExtractModal(false)
      setExtractData(null)
    } catch {
      message.error('入库失败')
    }
  }

  const handleShare = async () => {
    if (!conversation) {
      message.info('请先开始一段对话')
      return
    }
    try {
      const res = await chatApi.share(conversation.id)
      const url = `${window.location.origin}/share/${res.data.share_token}`
      await navigator.clipboard.writeText(url)
      message.success('分享链接已复制到剪贴板！')
    } catch {
      message.error('生成分享链接失败')
    }
  }

  const handleDeleteConv = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await request.delete(`/api/conversations/${convId}`)
      message.success('已删除')
      setConvList((prev) => prev.filter((c) => c.id !== convId))
      if (conversation?.id === convId) {
        setConversation(null)
        setMessages([])
      }
    } catch {
      message.error('删除失败')
    }
  }

  if (!initialized) {
    return <div className="kb-list-empty">加载中...</div>
  }

  return (
    <div className="chat-page chat-page--agent">
      <div className="chat-page__top-nav">
        <Button
          type="link"
          className="chat-page__nav-back"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(`/knowledge-bases/${kbId}`)}
        >
          返回详情
        </Button>
      </div>
      <HudPanel className="chat-page__panel">
        <div className="kb-detail__header">
          <div>
            <h2 className="page-title">AI 专家对话</h2>
            <p className="page-subtitle">基于知识库的智能问答终端</p>
          </div>
          <Space className="chat-page__toolbar" wrap>
            <Tooltip title="关闭 Cross-Encoder 重排、生成后质检与双路径一致性，保留 SIM-RAG/图谱多跳；检索仅 1 轮 CRAG">
              <label className="chat-fast-mode-switch">
                <ThunderboltOutlined className="chat-fast-mode-switch__icon" />
                <span className="chat-fast-mode-switch__label">快速模式</span>
                <Switch
                  size="small"
                  checked={fastMode}
                  onChange={(checked) => {
                    setFastMode(checked)
                    saveChatFastMode(kbId, checked)
                    message.info(checked ? '已开启快速模式' : '已关闭快速模式，将使用完整质量链路')
                  }}
                />
              </label>
            </Tooltip>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleNewChat}>
              新建对话
            </Button>
            <Button
              icon={<HistoryOutlined />}
              onClick={() => {
                setShowHistory(!showHistory)
                loadConvList()
              }}
            >
              历史
            </Button>
            <Button icon={<BulbOutlined />} onClick={handleExtract} loading={extracting}>
              提炼知识
            </Button>
            <Button icon={<ShareAltOutlined />} onClick={handleShare}>
              分享
            </Button>
          </Space>
        </div>

        {showHistory && (
          <div className="chat-history-panel">
            <div className="chat-history-panel__header">
              <span className="chat-history-panel__title">对话历史</span>
              <Button size="small" type="link" onClick={() => setShowHistory(false)}>
                关闭
              </Button>
            </div>
            <div className="chat-history-panel__list">
              {convList.map((c) => (
                <div
                  key={c.id}
                  className={`chat-history-item ${c.id === conversation?.id ? 'chat-history-item--active' : ''}`}
                  onClick={() => switchConversation(c)}
                  onKeyDown={(e) => e.key === 'Enter' && switchConversation(c)}
                  role="button"
                  tabIndex={0}
                >
                  <span className="chat-history-item__title">{c.title || '新对话'}</span>
                  <span className="chat-history-item__date">
                    {new Date(c.created_at).toLocaleDateString('zh-CN')}
                  </span>
                  <Popconfirm
                    title="确定删除该对话？"
                    onConfirm={(e) => handleDeleteConv(c.id, e as unknown as React.MouseEvent)}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      size="small"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                      style={{ marginLeft: 'auto', flexShrink: 0 }}
                    />
                  </Popconfirm>
                </div>
              ))}
              {convList.length === 0 && (
                <Typography.Text type="secondary">暂无历史对话</Typography.Text>
              )}
              {convHasMore && (
                <Button
                  size="small"
                  block
                  type="link"
                  onClick={async () => {
                    if (!kbId) return
                    const more = (
                      await chatApi.listConversations(kbId, CONV_LIST_PAGE_SIZE, convList.length)
                    ).data
                    setConvList((prev) => [...prev, ...more])
                    setConvHasMore(more.length >= CONV_LIST_PAGE_SIZE)
                  }}
                >
                  加载更多
                </Button>
              )}
            </div>
          </div>
        )}

        <div className="chat-page__body">
          <ChatWindow
            messages={messages}
            input={input}
            sending={sending}
            kbId={kbId}
            onInputChange={setInput}
            onSend={handleSend}
            onFeedback={handleFeedback}
          />
        </div>

        <Modal
          title="提炼为知识"
          open={extractModal}
          onOk={confirmExtract}
          onCancel={() => {
            setExtractModal(false)
            setExtractData(null)
          }}
          okText="确认录入"
          cancelText="取消"
        >
          {extractData && (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text strong>标题：{extractData.title}</Typography.Text>
              {extractData.source_ref && (
                <Typography.Text type="secondary">
                  来源引用：{extractData.source_ref}
                </Typography.Text>
              )}
              {extractData.manual_required ? (
                <Typography.Text type="warning">
                  知识缺失类缺口，请到补全任务人工添加
                </Typography.Text>
              ) : (
                <Typography.Paragraph
                  ellipsis={{ rows: 6, expandable: true }}
                  style={{
                    whiteSpace: 'pre-wrap',
                    background: 'var(--bg-void)',
                    padding: 12,
                    borderRadius: 8,
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  {extractData.content}
                </Typography.Paragraph>
              )}
            </Space>
          )}
        </Modal>
      </HudPanel>
    </div>
  )
}
