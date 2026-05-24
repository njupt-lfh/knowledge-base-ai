import request from './request'
import type { Conversation, Message } from '../types'

export const chatApi = {
  createConversation: (kbId: string) =>
    request.post<Conversation>(`/api/knowledge-bases/${kbId}/chat`),

  listConversations: (kbId: string) =>
    request.get<Conversation[]>(`/api/knowledge-bases/${kbId}/conversations`),

  getMessages: (convId: string) =>
    request.get<Message[]>(`/api/conversations/${convId}/messages`),

  sendMessage: async function* (convId: string, message: string) {
    const response = await fetch(`http://localhost:8080/api/conversations/${convId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, knowledge_base_id: '' }),
    })

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) return

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
            // ignore parse errors
          }
        }
      }
    }
  },

  share: (convId: string) =>
    request.post<{ share_token: string; share_url: string }>(`/api/conversations/${convId}/share`),

  getByShareToken: (token: string) =>
    request.get<Conversation>(`/api/share/${token}`),
}
