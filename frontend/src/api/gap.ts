import request from './request'

export interface KnowledgeGap {
  id: string
  kb_id: string
  query: string
  conversation_id: string | null
  message_id: string | null
  gap_type: string
  status: string
  suggested_content: string | null
  source_ref: string | null
  confidence: number | null
  created_at: string
}

export const gapApi = {
  list: (kbId: string, params?: { gap_type?: string; status?: string }) =>
    request.get<KnowledgeGap[]>(`/api/knowledge-bases/${kbId}/gaps`, { params }),

  create: (kbId: string, body: { query: string; gap_type?: string; correction_text?: string }) =>
    request.post<KnowledgeGap>(`/api/knowledge-bases/${kbId}/gaps`, body),

  updateStatus: (kbId: string, gapId: string, status: string) =>
    request.patch<KnowledgeGap>(`/api/knowledge-bases/${kbId}/gaps/${gapId}/status`, { status }),
}
