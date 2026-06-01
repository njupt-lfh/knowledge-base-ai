/**
 * 知识库治理 API
 * 扫描重复/冷知识/低质量块并执行治理动作
 * 主要导出：GovernanceSuggestion、GovernanceHealth、GovernanceScanResult、governanceApi
 */
import request from './request'

/** 单条治理建议 */
export interface GovernanceSuggestion {
  id: string
  type: string
  title: string
  description: string
  chunk_ids: string[]
  recommended_action: string
  severity: 'info' | 'warning' | 'error'
  content_preview: string
}

/** 治理扫描健康摘要 */
export interface GovernanceHealth {
  cold_count_90d: number
  cold_count_total: number
  threshold_days: number
  total_chunks: number
  active_chunks: number
  suggestions_count: number
}

/** 完整治理扫描结果 */
export interface GovernanceScanResult {
  kb_id: string
  scanned_at: string
  health: GovernanceHealth
  suggestions: GovernanceSuggestion[]
}

export const governanceApi = {
  /** 获取治理建议列表，可选是否扫描重复 */
  scan: (kbId: string, scanDuplicates = true) =>
    request.get<GovernanceScanResult>(`/api/knowledge-bases/${kbId}/governance/suggestions`, {
      params: { scan_duplicates: scanDuplicates },
    }),

  /** 对指定 chunk 批量执行治理动作（归档/禁用等） */
  apply: (kbId: string, action: string, chunkIds: string[]) =>
    request.post<{ action: string; applied: number; details: string[] }>(
      `/api/knowledge-bases/${kbId}/governance/actions`,
      { action, chunk_ids: chunkIds },
    ),
}
