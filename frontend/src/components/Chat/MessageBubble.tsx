/**
 * 单条聊天气泡
 * 展示消息正文、Agent 元信息、引用来源与用户反馈
 * 主要导出：ChatMessageData 类型、默认 MessageBubble 组件
 */
import { useState } from 'react'
import { Button, Input, Space, message as antdMessage } from 'antd'
import { DislikeOutlined, EditOutlined, LikeOutlined } from '@ant-design/icons'
import type { SourceItem } from '../../types'
import { feedbackApi } from '../../api/feedback'
import SourceTags from './SourceTags'
import AgentMetaStrip, { type AgentMeta } from './AgentMetaStrip'
import './Chat.css'

/** 前端聊天消息结构（含流式与反馈状态） */
export interface ChatMessageData {
  id?: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceItem[]
  isStreaming?: boolean
  feedback?: 'like' | 'dislike' | 'correction'
  agentMeta?: AgentMeta
}

interface MessageBubbleProps {
  message: ChatMessageData
  kbId?: string
  onFeedback?: (messageId: string, type: 'like' | 'dislike' | 'correction') => void
}

/**
 * 渲染单条用户/助手消息
 * @param kbId 知识库 ID，反馈 API 必需
 * @param onFeedback 反馈成功后的本地状态更新回调
 */
export default function MessageBubble({ message, kbId, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const [correcting, setCorrecting] = useState(false)
  const [correctionText, setCorrectionText] = useState('')

  const submitFeedback = async (type: 'like' | 'dislike' | 'correction', text?: string) => {
    if (!kbId || !message.id) {
      antdMessage.info('请发送消息后再评价')
      return
    }
    try {
      const chunkIds = (message.sources || [])
        .map((s) => s.chunk_id)
        .filter((id): id is string => Boolean(id))
      await feedbackApi.submit(kbId, {
        message_id: message.id,
        feedback_type: type,
        chunk_ids: chunkIds.length > 0 ? chunkIds : undefined,
        correction_text: text,
      })
      onFeedback?.(message.id, type)
      antdMessage.success(type === 'like' ? '感谢反馈' : '已记录反馈')
      setCorrecting(false)
    } catch {
      antdMessage.error('提交反馈失败')
    }
  }

  return (
    <div className={`message-bubble message-bubble--${message.role}`}>
      <div className="message-bubble__wrapper">
        <div className="message-bubble__role-label">{isUser ? 'USER' : 'ASSISTANT'}</div>
        <div className="message-bubble__content">
          {message.content}
          {message.isStreaming && <span className="message-bubble__cursor">▍</span>}
        </div>
        {!isUser && message.agentMeta && <AgentMetaStrip meta={message.agentMeta} />}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceTags sources={message.sources} />
        )}
        {!isUser && !message.isStreaming && message.id && (
          <div className="message-bubble__feedback">
            <Space size="small">
              <Button
                size="small"
                type={message.feedback === 'like' ? 'primary' : 'text'}
                icon={<LikeOutlined />}
                onClick={() => submitFeedback('like')}
              />
              <Button
                size="small"
                type={message.feedback === 'dislike' ? 'primary' : 'text'}
                icon={<DislikeOutlined />}
                onClick={() => submitFeedback('dislike')}
              />
              <Button
                size="small"
                type="text"
                icon={<EditOutlined />}
                onClick={() => setCorrecting(!correcting)}
              />
            </Space>
            {correcting && (
              <Space.Compact style={{ marginTop: 8, width: '100%' }}>
                <Input
                  placeholder="纠正内容..."
                  value={correctionText}
                  onChange={(e) => setCorrectionText(e.target.value)}
                />
                <Button type="primary" onClick={() => submitFeedback('correction', correctionText)}>
                  提交
                </Button>
              </Space.Compact>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
