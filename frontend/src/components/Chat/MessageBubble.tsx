import type { SourceItem } from '../../types'
import SourceTags from './SourceTags'
import './Chat.css'

export interface ChatMessageData {
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  isStreaming?: boolean
}

interface MessageBubbleProps {
  message: ChatMessageData
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`message-bubble message-bubble--${message.role}`}>
      <div className="message-bubble__wrapper">
        <div className="message-bubble__role-label">
          {isUser ? 'USER' : 'ASSISTANT'}
        </div>
        <div className="message-bubble__content">
          {message.content}
          {message.isStreaming && <span className="message-bubble__cursor">▍</span>}
        </div>
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceTags sources={message.sources} />
        )}
      </div>
    </div>
  )
}
