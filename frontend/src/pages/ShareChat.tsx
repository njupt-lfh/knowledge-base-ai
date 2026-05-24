import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { Card, Input, Button, Space, Typography, message } from 'antd'
import { SendOutlined, RobotOutlined } from '@ant-design/icons'
import type { Conversation, Message } from '../types'

const API_BASE = 'http://localhost:8080'

async function* streamChat(convId: string, msg: string) {
  const r = await fetch(`${API_BASE}/api/conversations/${convId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: msg, knowledge_base_id: '' }),
  })
  const reader = r.body?.getReader()
  if (!reader) return
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try { yield JSON.parse(line.slice(6)) } catch { /* skip */ }
      }
    }
  }
}

export default function ShareChat() {
  const { token } = useParams<{ token: string }>()
  const [conv, setConv] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    fetch(`${API_BASE}/api/share/${token}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.detail) { setError('分享链接无效或已过期'); return }
        setConv(data)
        return fetch(`${API_BASE}/api/conversations/${data.id}/messages`)
      })
      .then((r) => r?.json())
      .then((msgs: Message[]) => {
        if (msgs) setMessages(msgs.map((m) => ({ role: m.role, content: m.content })))
      })
      .catch(() => setError('加载失败'))
  }, [token])

  const scrollToBottom = () => {
    setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
  }

  const handleSend = async () => {
    if (sending || !input.trim() || !conv) return
    setMessages((prev) => [...prev, { role: 'user', content: input }])
    const q = input
    setInput('')
    setSending(true)

    const assistantIdx = messages.length + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])
    scrollToBottom()

    try {
      for await (const evt of streamChat(conv.id, q)) {
        if (evt.type === 'text') {
          setMessages((prev) => prev.map((m, i) =>
            i === assistantIdx ? { ...m, content: m.content + evt.content } : m,
          ))
          scrollToBottom()
        }
      }
    } catch { message.error('发送失败') }
    setSending(false)
  }

  if (error) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Card>
          <Typography.Text type="danger">{error}</Typography.Text>
        </Card>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 24 }}>
      <Card
        title={
          <Space>
            <RobotOutlined />
            AI 专家对话
            <Typography.Text type="secondary">（分享）</Typography.Text>
          </Space>
        }
      >
        <div style={{
          height: 500, overflowY: 'auto', border: '1px solid #f0f0f0',
          borderRadius: 8, padding: 16, marginBottom: 16, background: '#fafafa',
        }}>
          {messages.map((msg, idx) => (
            <div key={idx} style={{ marginBottom: 16 }}>
              <div style={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }}>
                <div style={{
                  maxWidth: '80%', padding: '8px 16px', borderRadius: 12,
                  background: msg.role === 'user' ? '#1677ff' : '#fff',
                  color: msg.role === 'user' ? '#fff' : '#000',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                }}>
                  <Typography.Text style={{ color: msg.role === 'user' ? '#fff' : '#000', whiteSpace: 'pre-wrap' }}>
                    {msg.content}
                  </Typography.Text>
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={handleSend}
            placeholder="输入问题..."
            disabled={sending}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={sending} disabled={sending}>
            发送
          </Button>
        </Space.Compact>
      </Card>
    </div>
  )
}
