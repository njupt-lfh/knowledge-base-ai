import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Input, Button, Space, Typography, Tag, message, Modal } from 'antd'
import { SendOutlined, ArrowLeftOutlined, ShareAltOutlined, BulbOutlined } from '@ant-design/icons'
import { chatApi } from '../api/chat'
import request from '../api/request'
import type { Conversation, Message, SourceItem } from '../types'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  isStreaming?: boolean
}

export default function ChatAgent() {
  const { kbId } = useParams<{ kbId: string }>()
  const navigate = useNavigate()
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [convList, setConvList] = useState<Conversation[]>([])
  const [showHistory, setShowHistory] = useState(false)

  const loadConvList = useCallback(async () => {
    if (!kbId) return
    try { setConvList((await chatApi.listConversations(kbId)).data) } catch { /* ok */ }
  }, [kbId])

  const initConversation = useCallback(async () => {
    try {
      const res = await chatApi.createConversation(kbId!)
      setConversation(res.data)
      loadConvList()
    } catch { message.error('创建对话失败') }
  }, [kbId, loadConvList])

  const switchConversation = async (conv: Conversation) => {
    setConversation(conv)
    setShowHistory(false)
    try {
      const msgs = (await chatApi.getMessages(conv.id)).data
      setMessages(msgs.map((m: Message) => ({ role: m.role, content: m.content, sources: m.sources ?? undefined })))
    } catch { message.error('加载消息失败') }
  }

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (kbId) { initConversation(); loadConvList() }
  }, [kbId, initConversation, loadConvList])
  /* eslint-enable react-hooks/set-state-in-effect */

  const scrollToBottom = () => {
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
  }

  const handleSend = async () => {
    if (sending || !input.trim() || !conversation) return
    const userMsg: ChatMessage = { role: 'user', content: input }
    const assistantMsg: ChatMessage = { role: 'assistant', content: '', isStreaming: true }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    setSending(true)
    scrollToBottom()

    try {
      for await (const event of chatApi.sendMessage(conversation.id, input)) {
        if (event.type === 'text') {
          setMessages((prev) =>
            prev.map((msg, i) =>
              i === prev.length - 1 && msg.role === 'assistant'
                ? { ...msg, content: msg.content + event.content }
                : msg,
            ),
          )
          scrollToBottom()
        } else if (event.type === 'sources') {
          setMessages((prev) =>
            prev.map((msg, i) =>
              i === prev.length - 1 && msg.role === 'assistant'
                ? { ...msg, sources: event.sources }
                : msg,
            ),
          )
        } else if (event.type === 'done') {
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
  }

  const [extractModal, setExtractModal] = useState(false)
  const [extractData, setExtractData] = useState<{ title: string; content: string; kb_id: string } | null>(null)
  const [extracting, setExtracting] = useState(false)

  const handleExtract = async () => {
    if (!conversation) return
    setExtracting(true)
    try {
      const res = await request.post(`/api/conversations/${conversation.id}/extract-knowledge`)
      if (res.data.has_knowledge) {
        setExtractData(res.data)
        setExtractModal(true)
      } else {
        message.info('当前对话未检测到新知识点')
      }
    } catch { message.error('知识提炼失败') }
    setExtracting(false)
  }

  const confirmExtract = async () => {
    if (!extractData || !conversation) return
    try {
      await request.post(`/api/knowledge-bases/${extractData.kb_id}/documents/manual`, {
        title: extractData.title,
        content: extractData.content,
      })
      message.success('知识已录入知识库！')
      setExtractModal(false)
      setExtractData(null)
    } catch { message.error('录入失败') }
  }

  const handleShare = async () => {
    if (!conversation) return
    try {
      const res = await chatApi.share(conversation.id)
      const url = `${window.location.origin}/share/${res.data.share_token}`
      await navigator.clipboard.writeText(url)
      message.success('分享链接已复制到剪贴板！')
    } catch { message.error('生成分享链接失败') }
  }

  return (
    <Card
      title="AI 专家对话"
      extra={
        <Space>
          <Button onClick={() => { setShowHistory(!showHistory); loadConvList() }}>历史</Button>
          <Button icon={<BulbOutlined />} onClick={handleExtract} loading={extracting}>提炼知识</Button>
          <Button icon={<ShareAltOutlined />} onClick={handleShare}>分享</Button>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/knowledge-bases')}>返回</Button>
        </Space>
      }
    >
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        {showHistory && (
          <Card size="small" title="对话历史" style={{ marginBottom: 16 }}
            extra={<Button size="small" type="link" onClick={() => { setShowHistory(false) }}>关闭</Button>}>
            {convList.map((c) => (
              <div key={c.id} style={{
                padding: '8px 12px', cursor: 'pointer', borderRadius: 6,
                background: c.id === conversation?.id ? '#e6f4ff' : 'transparent',
                marginBottom: 4,
              }} onClick={() => switchConversation(c)}>
                <Typography.Text>{c.title || '新对话'}</Typography.Text>
                <Typography.Text type="secondary" style={{ float: 'right', fontSize: 12 }}>
                  {new Date(c.created_at).toLocaleDateString('zh-CN')}
                </Typography.Text>
              </div>
            ))}
            {convList.length === 0 && <Typography.Text type="secondary">暂无历史对话</Typography.Text>}
          </Card>
        )}
        <div style={{
          height: 500,
          overflowY: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
          background: '#fafafa',
        }}>
          {messages.length === 0 && (
            <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', marginTop: 200 }}>
              输入问题开始与知识库对话...
            </Typography.Text>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} style={{ marginBottom: 16 }}>
              <div style={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }}>
                <div style={{
                  maxWidth: '80%',
                  padding: '8px 16px',
                  borderRadius: 12,
                  background: msg.role === 'user' ? '#1677ff' : '#fff',
                  color: msg.role === 'user' ? '#fff' : '#000',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                }}>
                  <Typography.Text style={{ color: msg.role === 'user' ? '#fff' : '#000', whiteSpace: 'pre-wrap' }}>
                    {msg.content}
                    {msg.isStreaming && <span style={{ animation: 'blink 1s infinite' }}>▍</span>}
                  </Typography.Text>
                </div>
              </div>
              {msg.sources && msg.sources.length > 0 && (
                <div style={{ marginTop: 8, marginLeft: 8 }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    引用来源：
                  </Typography.Text>
                  {msg.sources.map((s, si) => (
                    <Tag key={si} color="blue" style={{ marginTop: 4, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      [{s.score.toFixed(2)}] {s.content.slice(0, 60)}...
                    </Tag>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handleSend}
            placeholder="输入您的问题..."
            disabled={sending}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={sending} disabled={sending}>
            发送
          </Button>
        </Space.Compact>

        <Modal
          title="提炼为知识"
          open={extractModal}
          onOk={confirmExtract}
          onCancel={() => { setExtractModal(false); setExtractData(null) }}
          okText="确认录入"
          cancelText="取消"
        >
          {extractData && (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text strong>标题：{extractData.title}</Typography.Text>
              <Typography.Paragraph
                ellipsis={{ rows: 6, expandable: true }}
                style={{ whiteSpace: 'pre-wrap', background: '#fafafa', padding: 12, borderRadius: 8 }}
              >
                {extractData.content}
              </Typography.Paragraph>
            </Space>
          )}
        </Modal>
      </div>
    </Card>
  )
}
