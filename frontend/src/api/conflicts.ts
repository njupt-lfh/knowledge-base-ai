import request from './request'

export interface KnowledgeConflict {
  id: string
  kb_id: string
  existing_chunk_id: string
  existing_preview: string
  new_content: string
  new_preview: string
  similarity: number
  status: string
  llm_reason: string | null
  source_document_id: string | null
  resolved_chunk_id: string | null
  created_at: string | null
  resolved_at: string | null
}

export interface IngestPrecheckResult {
  status: string
  duplicate_of: string | null
  similarity: number | null
  llm_calls: number
  message: string | null
}

export const conflictsApi = {
  list: (kbId: string, status = 'pending') =>
    request.get<KnowledgeConflict[]>(`/api/knowledge-bases/${kbId}/conflicts`, { params: { status } }),

  resolve: (kbId: string, conflictId: string, resolution: string) =>
    request.post<KnowledgeConflict>(
      `/api/knowledge-bases/${kbId}/conflicts/${conflictId}/resolve`,
      { resolution },
    ),

  precheck: (kbId: string, content: string) =>
    request.post<IngestPrecheckResult>(`/api/knowledge-bases/${kbId}/ingestion/precheck`, { content }),
}
