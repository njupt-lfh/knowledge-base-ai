/**
 * 入库冲突 API
 * 相似度区间内的矛盾检测与人工裁决
 * 主要导出：KnowledgeConflict、IngestPrecheckResult、conflictsApi
 */
import request from './request'
import type { GovernanceChunkRef } from './governance'

/** 待裁决的知识冲突记录 */
export interface KnowledgeConflict {
  id: string
  kb_id: string
  existing_chunk_id: string
  existing_chunk_ref?: GovernanceChunkRef | null
  existing_preview: string
  new_content: string
  new_preview: string
  similarity: number
  status: string
  llm_reason: string | null
  source_document_id: string | null
  source_document_name?: string | null
  resolved_chunk_id: string | null
  resolved_chunk_ref?: GovernanceChunkRef | null
  created_at: string | null
  resolved_at: string | null
}

export type ConflictListStatus =
  | 'pending'
  | 'history'
  | 'resolved_keep_new'
  | 'resolved_keep_old'
  | 'dismissed'

/** 手动录入前的门禁预检结果 */
export interface IngestPrecheckResult {
  status: string
  duplicate_of: string | null
  similarity: number | null
  llm_calls: number
  message: string | null
}

export const conflictsApi = {
  list: (kbId: string, status: ConflictListStatus = 'pending', limit = 50) =>
    request.get<KnowledgeConflict[]>(`/api/knowledge-bases/${kbId}/conflicts`, {
      params: { status, limit },
    }),

  resolve: (kbId: string, conflictId: string, resolution: string) =>
    request.post<KnowledgeConflict>(
      `/api/knowledge-bases/${kbId}/conflicts/${conflictId}/resolve`,
      { resolution },
    ),

  rollback: (kbId: string, conflictId: string) =>
    request.post<KnowledgeConflict & { prev_status?: string }>(
      `/api/knowledge-bases/${kbId}/conflicts/${conflictId}/rollback`,
    ),

  precheck: (kbId: string, content: string) =>
    request.post<IngestPrecheckResult>(`/api/knowledge-bases/${kbId}/ingestion/precheck`, {
      content,
    }),
}
