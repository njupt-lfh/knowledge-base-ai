/**
 * 统计数据 API
 * 全局概览、趋势、热力图及单库深度指标
 * 主要导出：StatsOverview、TrendPoint、KBStats、statsApi 等类型与 API
 */
import request from './request'

export interface StatsOverview {
  kb_count: number
  doc_count: number
  chunk_count: number
  total_hits: number
  top_chunks: { content: string; hits: number }[]
  kb_distribution?: { name: string; doc_count: number; chunk_count: number }[]
  cold_knowledge?: ColdKnowledgeStats
}

export interface TrendPoint {
  date: string
  hits: number
}

export interface KBStats {
  document_count: number
  chunk_count: number
  total_hits: number
  hot_items: {
    chunk_id: string
    content: string
    hit_count: number
    chunk_index: number
    document_id: string
  }[]
}

export interface HitBucket {
  label: string
  count: number
}

export interface CiteHitItem {
  chunk_id: string
  label: string
  hit_count: number
  cite_count: number
}

export interface SankeyNode {
  name: string
  label: string
}

export interface SankeyLink {
  source: string
  target: string
  value: number
}

export interface ActivityPoint {
  dow: number
  hour: number
  count: number
}

export interface DocTypeItem {
  type: string
  name: string
  count: number
}

export interface ColdKnowledgeStats {
  cold_count_90d: number
  cold_count_total: number
  threshold_days: number
}

/** 单库高级统计聚合（分布、引用对比、桑基、冷知识） */
export interface KBAdvancedStats {
  distribution: HitBucket[]
  citeVsHit: CiteHitItem[]
  sankey: { nodes: SankeyNode[]; links: SankeyLink[] }
  cold: ColdKnowledgeStats
}

export const statsApi = {
  overview: () => request.get<StatsOverview>('/api/stats/overview'),
  trend: (days = 7, kbId?: string) =>
    request.get<{ points: TrendPoint[] }>('/api/stats/trend', {
      params: { days, kb_id: kbId },
    }),
  kbStats: (kbId: string) => request.get<KBStats>(`/api/knowledge-bases/${kbId}/stats`),
  docTypes: (kbId: string) =>
    request.get<{ items: DocTypeItem[] }>(`/api/knowledge-bases/${kbId}/stats/doc-types`),
  hitDistribution: (kbId: string) =>
    request.get<{ buckets: HitBucket[] }>(`/api/knowledge-bases/${kbId}/stats/distribution`),
  citeVsHit: (kbId: string, limit = 10) =>
    request.get<{ items: CiteHitItem[] }>(`/api/knowledge-bases/${kbId}/stats/cite-vs-hit`, {
      params: { limit },
    }),
  sankey: (kbId: string, limit = 15) =>
    request.get<{ nodes: SankeyNode[]; links: SankeyLink[] }>(
      `/api/knowledge-bases/${kbId}/stats/sankey`,
      { params: { limit } },
    ),
  activityHeatmap: (kbId?: string, days = 30) =>
    request.get<{ points: ActivityPoint[] }>('/api/stats/activity-heatmap', {
      params: { kb_id: kbId, days },
    }),
  coldKnowledge: (kbId?: string) =>
    request.get<ColdKnowledgeStats>('/api/stats/cold-knowledge', { params: { kb_id: kbId } }),

  /** 并行拉取单库四项深度指标并组装为 KBAdvancedStats */
  kbAdvanced: async (kbId: string): Promise<KBAdvancedStats> => {
    const [dist, cite, sankey, cold] = await Promise.all([
      statsApi.hitDistribution(kbId),
      statsApi.citeVsHit(kbId),
      statsApi.sankey(kbId),
      statsApi.coldKnowledge(kbId),
    ])
    return {
      distribution: dist.data.buckets,
      citeVsHit: cite.data.items,
      sankey: sankey.data,
      cold: cold.data,
    }
  },
}
