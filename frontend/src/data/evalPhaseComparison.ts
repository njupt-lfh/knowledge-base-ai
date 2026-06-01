/**
 * 检索评测阶段对比静态数据（只读快照）
 * 来源：工作记录/答辩-检索评测对比表.md · 2026-05-26
 * 评测集：5 库 × 20 条 = 100 条 · 口径：run_rag_eval.py --retrieval-only
 * 主要导出：PhaseKey、PhaseComparisonRow、EVAL_COMPARISON_META、
 *   RETRIEVAL_COMPARISON_ROWS、MULTIHOP_COMPARISON_ROWS、PHASE_LABELS
 */

/** 演进阶段标识 */
export type PhaseKey = 'phase0' | 'phase2' | 'phase3'

export interface PhaseComparisonRow {
  key: string
  metric: string
  hint?: string
  phase0: string
  phase2: string
  phase3: string
  /** 从当前 eval_baseline_report.json 读取的字段名（若有） */
  liveField?:
    | 'context_recall_mean'
    | 'context_precision_mean'
    | 'retrieval_hit_rate'
    | 'negative_reject_rate'
    | 'avg_retrieve_ms'
  /** 为 true 时「当前报告」列显示静态 phase3（无对应 live 字段） */
  staticLive?: boolean
  format?: 'percent' | 'ms' | 'decimal'
}

export const EVAL_COMPARISON_META = {
  sampleSet: '100 条（fact 50 / concept 20 / multi_hop 20 / negative 10）',
  updatedAt: '2026-05-26',
  sourceNote:
    'Phase 0～3 为阶段出口快照；「当前报告」随页面加载的 eval_baseline_report.json 更新。',
}

export const RETRIEVAL_COMPARISON_ROWS: PhaseComparisonRow[] = [
  {
    key: 'recall_all',
    metric: '上下文召回率（全样本）',
    phase0: '0.810',
    phase2: '0.880',
    phase3: '0.885',
    liveField: 'context_recall_mean',
    format: 'decimal',
  },
  {
    key: 'recall_pos',
    metric: '上下文召回率（正例 90 条）',
    phase0: '0.844',
    phase2: '0.944',
    phase3: '0.906',
    staticLive: true,
    format: 'decimal',
  },
  {
    key: 'hit_rate',
    metric: '检索命中率（正例）',
    phase0: '0.867',
    phase2: '0.978',
    phase3: '0.944',
    liveField: 'retrieval_hit_rate',
    format: 'decimal',
  },
  {
    key: 'precision',
    metric: '上下文精确率',
    phase0: '0.275',
    phase2: '0.242',
    phase3: '—',
    liveField: 'context_precision_mean',
    format: 'decimal',
  },
  {
    key: 'neg_empty',
    metric: '负例空检索率（10 条）',
    hint: '无关问题返回空检索的比例，越高越好',
    phase0: '50%',
    phase2: '30%',
    phase3: '70%',
    staticLive: true,
  },
  {
    key: 'latency',
    metric: '平均检索延迟',
    phase0: '~774 ms',
    phase2: '~734 ms',
    phase3: '~734 ms',
    liveField: 'avg_retrieve_ms',
    format: 'ms',
  },
]

export const MULTIHOP_COMPARISON_ROWS = [
  { key: 'mh_vector', mode: '纯向量（Phase 0 基线）', recall: '0.800', delta: '—' },
  { key: 'mh_hybrid', mode: 'Hybrid（Phase 2）', recall: '0.850', delta: '+6.3%' },
  { key: 'mh_graph', mode: 'Agent + 图谱（Phase 3）', recall: '0.825', delta: '+3.1%' },
]

export const PHASE_LABELS: Record<PhaseKey, string> = {
  phase0: 'Phase 0\n向量检索',
  phase2: 'Phase 2\nHybrid + Agent',
  phase3: 'Phase 3\n图谱 + Abstention',
}
