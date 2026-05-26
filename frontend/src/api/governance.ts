import request from './request'

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

export interface GovernanceHealth {
  cold_count_90d: number
  cold_count_total: number
  threshold_days: number
  total_chunks: number
  active_chunks: number
  suggestions_count: number
}

export interface GovernanceScanResult {
  kb_id: string
  scanned_at: string
  health: GovernanceHealth
  suggestions: GovernanceSuggestion[]
}

export const governanceApi = {
  scan: (kbId: string, scanDuplicates = true) =>
    request.get<GovernanceScanResult>(`/api/knowledge-bases/${kbId}/governance/suggestions`, {
      params: { scan_duplicates: scanDuplicates },
    }),

  apply: (kbId: string, action: string, chunkIds: string[]) =>
    request.post<{ action: string; applied: number; details: string[] }>(
      `/api/knowledge-bases/${kbId}/governance/actions`,
      { action, chunk_ids: chunkIds },
    ),
}
