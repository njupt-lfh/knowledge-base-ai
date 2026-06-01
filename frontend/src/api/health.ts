/**
 * 知识库健康度 API
 * 综合冷知识、缺口、冲突、低质量块等指标
 * 主要导出：KnowledgeBaseHealth、healthApi
 */
import request from './request'
import type { ColdKnowledgeStats } from './stats'

/** 知识库健康快照 */
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
