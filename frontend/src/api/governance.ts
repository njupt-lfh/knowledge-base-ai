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

/** 治理建议关联的知识块定位信息 */
export interface GovernanceChunkRef {
  chunk_id: string
  document_id: string
  document_name: string
  chunk_index: number
  is_active: boolean
  preview?: string
}

/** 持久化治理建议 */
export interface PersistedSuggestion {
  id: string
  kb_id: string
  suggestion_type: string
  title: string
  description: string
  chunk_ids: string // JSON array string
  chunk_refs?: GovernanceChunkRef[]
  recommended_action: string
  severity: string
  status: string
  created_at: string
  approved_at: string | null
  executed_at: string | null
  verified_at: string | null
  content_preview: string | null
}

/** 持久化治理建议列表（分页） */
export interface PersistedSuggestionList {
  items: PersistedSuggestion[]
  total: number
}

/** 兼容旧版直接返回数组的接口（数组时 total 不可信，请用 statusCounts） */
export function normalizePersistedList(
  data: PersistedSuggestionList | PersistedSuggestion[] | null | undefined,
): PersistedSuggestionList {
  if (!data) return { items: [], total: 0 }
  if (Array.isArray(data)) return { items: data, total: 0 }
  return {
    items: data.items ?? [],
    total: data.total ?? 0,
  }
}

export type GovernanceStatusCounts = Record<string, number>

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

  /** 批量解析 chunk 所属文档与段落（列表缺 chunk_refs 时兜底） */
  resolveChunkRefs: (kbId: string, chunkIds: string[]) =>
    request.get<GovernanceChunkRef[]>(
      `/api/knowledge-bases/${kbId}/governance/chunk-refs`,
      { params: { ids: chunkIds.join(',') } },
    ),

  /** 各状态建议数量（Tab 角标） */
  statusCounts: (kbId: string) =>
    request.get<GovernanceStatusCounts>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/persisted/counts`,
    ),

  /** 列出已持久化的治理建议（含 total，默认每页 50 条） */
  listPersisted: async (
    kbId: string,
    params?: { status?: string; type?: string; limit?: number; offset?: number },
  ) => {
    const res = await request.get<PersistedSuggestionList | PersistedSuggestion[]>(
      `/api/knowledge-bases/${kbId}/governance/suggestions/persisted`,
      { params },
    )
    return { ...res, data: normalizePersistedList(res.data) }
  },

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
