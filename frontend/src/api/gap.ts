/**
 * 知识缺口（Gap）补全任务 API
 * 检索未命中、用户纠正等待入库队列
 * 主要导出：KnowledgeGap、gapApi
 */
import request from './request'

/** 单条补全任务 */
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

  /** 将 gap 建议内容经门禁入库，可选手动正文 */
  ingest: (
    kbId: string,
    gapId: string,
    body?: { manual_content?: string; manual_title?: string },
  ) =>
    request.post<{
      gap_id: string
      document_id: string
      ingest_allowed: number
      ingest_duplicates: number
      ingest_conflicts: number
    }>(`/api/knowledge-bases/${kbId}/gaps/${gapId}/ingest`, body || {}),
}
