import request from './request'

export interface GraphNode {
  id: string
  name: string
}

export interface GraphEdge {
  source: string
  target: string
  predicate: string
  chunk_id?: string
}

export interface KnowledgeGraphSnapshot {
  nodes: GraphNode[]
  edges: GraphEdge[]
  relation_count: number
  node_count: number
  empty?: boolean
}

export const graphApi = {
  getSnapshot: (kbId: string, limit = 80) =>
    request.get<KnowledgeGraphSnapshot>(`/api/knowledge-bases/${kbId}/graph`, {
      params: { limit },
    }),
}
