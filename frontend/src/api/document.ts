import request from './request'
import type { Document } from '../types'

export const documentApi = {
  list: (kbId: string, params?: { page?: number; page_size?: number }) =>
    request.get<{ items: Document[]; total: number }>(`/api/knowledge-bases/${kbId}/documents`, {
      params,
    }),

  upload: (kbId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post<Document>(`/api/knowledge-bases/${kbId}/documents/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  createManual: (kbId: string, data: { title: string; content: string }) =>
    request.post<Document>(`/api/knowledge-bases/${kbId}/documents/manual`, data),

  getById: (kbId: string, docId: string) =>
    request.get<Document>(`/api/knowledge-bases/${kbId}/documents/${docId}`),

  delete: (kbId: string, docId: string) =>
    request.delete(`/api/knowledge-bases/${kbId}/documents/${docId}`),

  toggleStatus: (kbId: string, docId: string, isActive: boolean) => {
    const formData = new FormData()
    formData.append('is_active', String(isActive))
    return request.put<Document>(`/api/knowledge-bases/${kbId}/documents/${docId}/status`, formData)
  },

  reindex: (kbId: string, docId: string) =>
    request.post<Document>(`/api/knowledge-bases/${kbId}/documents/${docId}/reindex`),
}
