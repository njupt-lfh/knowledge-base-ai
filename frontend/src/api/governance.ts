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

/** 持久化治理建议 */
export interface PersistedSuggestion {
  id: string
  kb_id: string
  suggestion_type: string
  title: string
  description: string
  chunk_ids: string // JSON array string
  recommended_action: string
  severity: string
  status: string
  created_at: string
  approved_at: string | null
  executed_at: string | null
  verified_at: string | null
  content_preview: string | null
}

/** 审计日志 */
export interface AuditLogEntry {
  id: string
  kb_id: string
  suggestion_id: string | null
  action: string
  operator: string | null
  detail: string | null
  created_at: string
}

export const governanceApi = {
  /** 实时扫描（不持久化） */
  scan: (kbId: string, scanDuplicates = true) =>
    request.get<GovernanceScanResult>(`/api/knowledge-bases/${kbId}/governance/suggestions`, {
      params: { scan_duplicates: scanDuplicates },
    }),

  /** 扫描 + 持久化（Phase 3 治理闭环） */
  scanAndPersist: (kbId: string, scanDuplicates = true) =>
    request.post<GovernanceScanResult & { scan_id: string; new_suggestions: number }>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/scan`,
      null,
      { params: { scan_duplicates: scanDuplicates } },
    ),

  /** 列出已持久化的治理建议 */
  listPersisted: (kbId: string, params?: { status?: string; type?: string }) =>
    request.get<PersistedSuggestion[]>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/persisted`,
      { params },
    ),

  /** 批准建议 */
  approve: (kbId: string, suggestionId: string) =>
    request.post<{ status: string; suggestion_id: string }>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/${suggestionId}/approve`,
    ),

  /** 驳回建议 */
  dismiss: (kbId: string, suggestionId: string, reason?: string) =>
    request.post<{ status: string; suggestion_id: string }>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/${suggestionId}/dismiss`,
      null,
      { params: { reason } },
    ),

  /** 执行已批准的建议 */
  execute: (kbId: string, suggestionId: string) =>
    request.post<{ status: string; suggestion_id: string; result: unknown }>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/${suggestionId}/execute`,
    ),

  /** 验证执行结果 */
  verify: (kbId: string, suggestionId: string) =>
    request.post<{ status: string; suggestion_id: string }>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/${suggestionId}/verify`,
    ),

  /** 直接 apply（保留旧接口） */
  apply: (kbId: string, action: string, chunkIds: string[]) =>
    request.post<{ action: string; applied: number; details: string[] }>(
      `/api/knowledge-bases/${kbId}/governance/actions`,
      { action, chunk_ids: chunkIds },
    ),

  /** 回退建议（误操作恢复） */
  rollback: (kbId: string, suggestionId: string) =>
    request.post<{ status: string; prev_status: string }>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/${suggestionId}/rollback`,
    ),

  /** 审计日志（可按动作筛选） */
  auditLog: (kbId: string, params?: { action?: string; limit?: number }) =>
    request.get<AuditLogEntry[]>(`/api/knowledge-bases/${kbId}/governance/audit-log`, {
      params: params || {},
    }),
}
