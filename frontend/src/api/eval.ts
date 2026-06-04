/**
 * RAG 评测基线 API
 * 读取 run_rag_eval.py 生成的基线报告
 * 主要导出：EvalBaselineReport、getReportSampleCount、evalApi
 */
import request from './request'

/** 评测基线报告结构（与后端 JSON 对齐） */
export interface EvalBaselineReport {
  version: string
  generated_at: string
  dataset_version?: string
  primary_kb_id?: string
  knowledge_bases?: Array<{ kb_id: string; kb_name: string; sample_count: number }>
  config?: {
    dataset?: string
    eval_mode?: string
    top_k?: number
    retrieval_only?: boolean
    ragas_enabled?: boolean
    llm_judge_enabled?: boolean
    limit?: number
    stratified?: boolean
    sample_count?: number
  }
  aggregate: {
    sample_count?: number
    context_recall_mean?: number | null
    context_recall_chunk?: number | null
    context_precision_mean?: number | null
    context_precision_chunk?: number | null
    context_precision_ragas?: number | null
    context_recall_ragas?: number | null
    mrr_mean?: number | null
    ndcg_at_5_mean?: number | null
    precision_at_1_mean?: number | null
    retrieval_hit_rate?: number | null
    negative_reject_rate?: number | null
    faithfulness_mean?: number | null
    answer_relevancy_mean?: number | null
    ragas?: Record<string, number | null>
    [key: string]: unknown
  }
  by_question_type?: Record<string, Record<string, unknown>>
  by_kb?: Record<string, Record<string, unknown> & { kb_name?: string }>
  diagnosis: { primary_bottleneck: string; recommendation: string }
  samples?: unknown[]
}

/**
 * 从报告中解析样本数
 * 优先级：aggregate > config > samples 数组长度
 * @param report 基线报告
 * @returns 样本数量或 undefined
 */
export function getReportSampleCount(report: EvalBaselineReport): number | undefined {
  return (
    report.aggregate?.sample_count ??
    report.config?.sample_count ??
    (report.samples?.length ? report.samples.length : undefined)
  )
}

export interface EvalTrendPoint {
  run_id: string
  created_at: string | null
  dataset_version: string
  eval_mode: string
  value: number | null
}

export interface EvalRunSummary {
  id: string
  created_at: string | null
  dataset_version: string
  eval_mode: string
  ci_phase: string | null
  sample_count: number
  aggregate: Record<string, unknown>
}

export const evalApi = {
  getBaseline: () => request.get<EvalBaselineReport>('/api/eval/baseline'),
  getRuns: (limit = 20) =>
    request.get<{ runs: EvalRunSummary[] }>(`/api/eval/runs?limit=${limit}`),
  getTrend: (metric: string, dataset?: string, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (dataset) params.set('dataset', dataset)
    return request.get<{ metric: string; points: EvalTrendPoint[] }>(
      `/api/eval/trend/${metric}?${params}`,
    )
  },
}
