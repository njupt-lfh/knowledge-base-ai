/**
 * 文件夹同步 API
 * 管理本地目录监听与扫描入库
 * 主要导出：FolderWatch、ScanResult、syncApi
 */
import request from './request'

/** 单个文件夹监听配置 */
export interface FolderWatch {
  id: string
  knowledge_base_id: string
  folder_path: string
  enabled: boolean
  recursive: boolean
  last_scan_at?: string | null
  last_error?: string | null
}

/** 单次扫描统计结果 */
export interface ScanResult {
  watch_id: string
  kb_id: string
  scanned: number
  imported: number
  updated: number
  skipped: number
  errors: string[]
}

export const syncApi = {
  listWatches: (kbId: string) =>
    request.get<FolderWatch[]>('/api/sync/watches', { params: { kb_id: kbId } }),

  createWatch: (data: {
    knowledge_base_id: string
    folder_path: string
    enabled?: boolean
    recursive?: boolean
  }) => request.post<FolderWatch>('/api/sync/watches', data),

  updateWatch: (watchId: string, data: { enabled?: boolean; recursive?: boolean }) =>
    request.patch<FolderWatch>(`/api/sync/watches/${watchId}`, data),

  deleteWatch: (watchId: string) => request.delete(`/api/sync/watches/${watchId}`),

  scanWatch: (watchId: string) => request.post<ScanResult>(`/api/sync/watches/${watchId}/scan`),

  scanKb: (kbId: string) => request.post<ScanResult[]>(`/api/sync/knowledge-bases/${kbId}/scan`),
}
