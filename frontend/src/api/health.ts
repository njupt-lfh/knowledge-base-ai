import request from './request'
import type { ColdKnowledgeStats } from './stats'

export interface KnowledgeBaseHealth {
  kb_id: string
  level: 'healthy' | 'attention' | 'critical'
  cold: ColdKnowledgeStats
  pending_gaps: number
  pending_conflicts: number
  low_quality_chunks: number
  total_chunks: number
  active_chunks: number
  attention_score: number
}

export const healthApi = {
  getKbHealth: (kbId: string) =>
    request.get<KnowledgeBaseHealth>(`/api/knowledge-bases/${kbId}/health`),
}
