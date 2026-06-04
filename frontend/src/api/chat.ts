/**
 * 对话相关 API
 * 含会话 CRUD、SSE 流式聊天、分享链接
 * 主要导出：chatApi
 */
import request from './request'
import type { Conversation, Message } from '../types'

export const chatApi = {
  /** 在指定知识库下创建新会话 */
  createConversation: (kbId: string) =>
    request.post<Conversation>(`/api/knowledge-bases/${kbId}/chat`),

  /** 分页列出知识库下的历史会话 */
  listConversations: (kbId: string, limit?: number, offset?: number) =>
    request.get<Conversation[]>(`/api/knowledge-bases/${kbId}/conversations`, {
      params: { limit, offset },
    }),

  /** 获取会话全部消息 */
  getMessages: (convId: string) => request.get<Message[]>(`/api/conversations/${convId}/messages`),

  /**
   * SSE 流式发送消息并逐条 yield 事件
   * @param convId 会话 ID
   * @param message 用户输入
   * @yields text / agent_meta / sources / done 等 JSON 事件
   */
  sendMessage: async function* (convId: string, message: string, fastMode = false) {
    const base = import.meta.env.VITE_API_BASE || 'http://localhost:8080'
    const response = await fetch(`${base}/api/conversations/${convId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, knowledge_base_id: '', fast_mode: fastMode }),
    })

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) return

    // 按行缓冲解析 SSE：data: {...}\n
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
            // 忽略单行 JSON 解析失败
          }
        }
      }
    }
  },

  /** 生成会话分享 token 与 URL */
  share: (convId: string) =>
    request.post<{ share_token: string; share_url: string }>(`/api/conversations/${convId}/share`),

  /** 通过分享 token 获取会话元数据 */
  getByShareToken: (token: string) => request.get<Conversation>(`/api/share/${token}`),
}
