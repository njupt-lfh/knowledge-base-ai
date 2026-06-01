/**
 * 知识库 CRUD API
 * 主要导出：knowledgeApi
 */
import request from './request'
import type { KnowledgeBase } from '../types'

export const knowledgeApi = {
  list: (params?: { page?: number; page_size?: number; search?: string }) =>
    request.get<{ items: KnowledgeBase[]; total: number }>('/api/knowledge-bases', { params }),

  create: (data: {
    name: string
    description?: string
    chunk_size?: number
    chunk_overlap?: number
  }) => request.post<KnowledgeBase>('/api/knowledge-bases', data),

  getById: (id: string) => request.get<KnowledgeBase>(`/api/knowledge-bases/${id}`),

  update: (id: string, data: Partial<KnowledgeBase>) =>
    request.put<KnowledgeBase>(`/api/knowledge-bases/${id}`, data),

  delete: (id: string) => request.delete(`/api/knowledge-bases/${id}`),
}
