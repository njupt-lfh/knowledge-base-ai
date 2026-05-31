import { useRef, useEffect } from 'react'
import { Input, Button } from 'antd'
import { SendOutlined, RobotOutlined } from '@ant-design/icons'
import MessageBubble, { type ChatMessageData } from './MessageBubble'
import './Chat.css'

interface ChatWindowProps {
  messages: ChatMessageData[]
  input: string
  sending: boolean
  kbId?: string
  disabled?: boolean
  placeholder?: string
  emptyHint?: string
  onInputChange: (value: string) => void
  onSend: () => void
  onFeedback?: (messageId: string, type: 'like' | 'dislike' | 'correction') => void
}

export default function ChatWindow({
  messages,
  input,
  sending,
  disabled = false,
  placeholder = '输入您的问题...',
  emptyHint = '输入问题开始与知识库对话，或点击「新建对话」',
  kbId,
  onInputChange,
  onSend,
  onFeedback,
}: ChatWindowProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-window">
      <div className="chat-window__messages">
        {messages.length === 0 ? (
          <div className="chat-window__empty">
            <RobotOutlined className="chat-window__empty-icon" />
            <span>{emptyHint}</span>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <MessageBubble key={msg.id || idx} message={msg} kbId={kbId} onFeedback={onFeedback} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-window__input">
        <Input
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onPressEnter={onSend}
          placeholder={placeholder}
          disabled={sending || disabled}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={onSend}
          loading={sending}
          disabled={sending || disabled || !input.trim()}
        >
          发送
        </Button>
      </div>
    </div>
  )
}
