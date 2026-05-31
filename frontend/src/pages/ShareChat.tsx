import { useEffect, useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { message } from 'antd'
import { DatabaseOutlined } from '@ant-design/icons'
import GridBackground from '../components/common/GridBackground'
import HudPanel from '../components/common/HudPanel'
import ThemeToggle from '../components/common/ThemeToggle'
import ChatWindow from '../components/Chat/ChatWindow'
import type { ChatMessageData } from '../components/Chat/MessageBubble'
import type { Conversation, Message, SourceItem } from '../types'
import '../components/Chat/Chat.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080'

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
        try {
          yield JSON.parse(line.slice(6))
        } catch {
          /* skip */
        }
      }
    }
  }
}

export default function ShareChat() {
  const { token } = useParams<{ token: string }>()
  const [conv, setConv] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<ChatMessageData[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const assistantIdxRef = useRef(-1)

  useEffect(() => {
    if (!token) return
    fetch(`${API_BASE}/api/share/${token}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.detail) {
          setError('分享链接无效或已过期')
          return
        }
        setConv(data)
        return fetch(`${API_BASE}/api/conversations/${data.id}/messages`)
      })
      .then((r) => r?.json())
      .then((msgs: Message[]) => {
        if (msgs) {
          setMessages(
            msgs.map((m) => ({
              role: m.role as 'user' | 'assistant',
              content: m.content,
              sources: m.sources ?? undefined,
            })),
          )
        }
      })
      .catch(() => setError('加载失败'))
  }, [token])

  const handleSend = async () => {
    if (sending || !input.trim() || !conv) return
    const userMsg: ChatMessageData = { role: 'user', content: input }
    const query = input
    setInput('')
    setSending(true)

    setMessages((prev) => {
      assistantIdxRef.current = prev.length + 1
      return [...prev, userMsg, { role: 'assistant', content: '', isStreaming: true }]
    })

    try {
      for await (const evt of streamChat(conv.id, query)) {
        if (evt.type === 'text') {
          setMessages((prev) =>
            prev.map((m, i) =>
              i === assistantIdxRef.current ? { ...m, content: m.content + evt.content } : m,
            ),
          )
        } else if (evt.type === 'sources') {
          setMessages((prev) =>
            prev.map((m, i) =>
              i === assistantIdxRef.current ? { ...m, sources: evt.sources as SourceItem[] } : m,
            ),
          )
        } else if (evt.type === 'done') {
          setMessages((prev) =>
            prev.map((m, i) => (i === assistantIdxRef.current ? { ...m, isStreaming: false } : m)),
          )
        }
      }
    } catch {
      message.error('发送失败')
    }
    setSending(false)
  }

  const content = error ? (
    <div className="share-page__error">
      <HudPanel style={{ padding: 32 }}>
        <span style={{ color: 'var(--accent-danger)', fontFamily: 'var(--font-mono)' }}>
          {error}
        </span>
      </HudPanel>
    </div>
  ) : (
    <div className="share-page">
      <GridBackground />
      <header className="share-page__topbar">
        <div className="share-page__brand">
          <DatabaseOutlined style={{ color: 'var(--accent-primary)' }} />
          KNOWLEDGE BASE AI
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ThemeToggle />
          <span className="share-page__badge">分享模式</span>
        </div>
      </header>
      <main className="share-page__content">
        <HudPanel className="chat-page__panel">
          <div className="kb-detail__header">
            <div>
              <h2 className="page-title">AI 专家对话</h2>
              <p className="page-subtitle">{conv?.title || '分享会话'}</p>
            </div>
          </div>
          <ChatWindow
            messages={messages}
            input={input}
            sending={sending}
            disabled={!conv}
            placeholder="输入问题继续对话..."
            emptyHint="加载对话中..."
            onInputChange={setInput}
            onSend={handleSend}
          />
        </HudPanel>
      </main>
    </div>
  )

  return content
}
