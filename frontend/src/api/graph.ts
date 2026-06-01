/**
 * 知识图谱 API
 * 获取实体-关系快照供力导向图展示
 * 主要导出：GraphNode、GraphEdge、KnowledgeGraphSnapshot、graphApi
 */
import request from './request'

/** 图谱节点（实体） */
export interface GraphNode {
  id: string
  name: string
}

/** 图谱边（关系三元组） */
export interface GraphEdge {
  source: string
  target: string
  predicate: string
  chunk_id?: string
}

/** 知识库图谱快照 */
export interface KnowledgeGraphSnapshot {
  nodes: GraphNode[]
  edges: GraphEdge[]
  relation_count: number
  node_count: number
  empty?: boolean
}

export const graphApi = {
  /** 获取知识库实体关系子图，limit 限制边数 */
  getSnapshot: (kbId: string, limit = 80) =>
    request.get<KnowledgeGraphSnapshot>(`/api/knowledge-bases/${kbId}/graph`, {
      params: { limit },
    }),
}
