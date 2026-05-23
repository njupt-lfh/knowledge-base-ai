import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Input, Button, Space, Typography, Tag, message } from 'antd'
import { SendOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { chatApi } from '../api/chat'
import type { Conversation } from '../types'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: { chunk_id: string; content: string; score: number }[]
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

  const initConversation = useCallback(async () => {
    try {
      const res = await chatApi.createConversation(kbId!)
      setConversation(res.data)
    } catch { message.error('创建对话失败') }
  }, [kbId])

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (kbId) initConversation()
  }, [kbId, initConversation])
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

  return (
    <Card
      title="AI 专家对话"
      extra={
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/knowledge-bases')}>
          返回
        </Button>
      }
    >
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
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
      </div>
    </Card>
  )
}
