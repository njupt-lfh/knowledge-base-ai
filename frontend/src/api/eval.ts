import request from './request'

export interface EvalBaselineReport {
  version: string
  generated_at: string
  primary_kb_id?: string
  knowledge_bases?: Array<{ kb_id: string; kb_name: string; sample_count: number }>
  config?: {
    top_k?: number
    retrieval_only?: boolean
    ragas_enabled?: boolean
    llm_judge_enabled?: boolean
    limit?: number
    sample_count?: number
  }
  aggregate: {
    sample_count?: number
    context_recall_mean?: number | null
    context_precision_mean?: number | null
    retrieval_hit_rate?: number | null
    negative_reject_rate?: number | null
    faithfulness_mean?: number | null
    answer_relevancy_mean?: number | null
    ragas?: Record<string, number | null>
    [key: string]: unknown
  }
  diagnosis: { primary_bottleneck: string; recommendation: string }
  samples?: unknown[]
}

/** 样本数：优先 aggregate，其次 config / samples 长度 */
export function getReportSampleCount(report: EvalBaselineReport): number | undefined {
  return (
    report.aggregate?.sample_count ??
    report.config?.sample_count ??
    (report.samples?.length ? report.samples.length : undefined)
  )
}

export const evalApi = {
  getBaseline: () => request.get<EvalBaselineReport>('/api/eval/baseline'),
}
