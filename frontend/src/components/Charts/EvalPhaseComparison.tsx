/**
 * 检索评测阶段对比表组件
 * 静态 Phase 0/2/3 快照与当前 eval 报告 live 字段对照
 * 主要导出：默认 EvalPhaseComparison 组件
 */
import { Table, Tag, Typography } from 'antd'
import type { EvalBaselineReport } from '../../api/eval'
import {
  EVAL_COMPARISON_META,
  MULTIHOP_COMPARISON_ROWS,
  PHASE_LABELS,
  RETRIEVAL_COMPARISON_ROWS,
  type PhaseComparisonRow,
} from '../../data/evalPhaseComparison'
import { formatDateTime } from '../../utils/format'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

/** 将 live 数值格式化为表格展示字符串 */
function formatLiveValue(
  value: number | null | undefined,
  format?: PhaseComparisonRow['format'],
): string {
  if (value == null || Number.isNaN(value)) return '—'
  if (format === 'ms') return `${Math.round(value)} ms`
  if (format === 'percent') return `${(value * 100).toFixed(0)}%`
  return value.toFixed(3)
}

function parsePhase0Number(phase0: string): number | null {
  const m = phase0.match(/[\d.]+/)
  if (!m) return null
  const n = parseFloat(m[0])
  return Number.isNaN(n) ? null : n
}

function calcDeltaVsP0(phase0: string, live: string): string {
  const base = parsePhase0Number(phase0)
  const cur = parseFloat(live)
  if (base == null || Number.isNaN(cur) || base === 0) return '—'
  const pct = ((cur - base) / base) * 100
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

interface EvalPhaseComparisonProps {
  report: EvalBaselineReport | null
}

/** 检索演进对比主组件，依赖 eval 基线 aggregate 字段 */
export default function EvalPhaseComparison({ report }: EvalPhaseComparisonProps) {
  const agg = report?.aggregate ?? {}

  const resolveLive = (row: PhaseComparisonRow): string => {
    if (row.staticLive) return row.phase3
    if (!row.liveField) return '—'
    return formatLiveValue(agg[row.liveField] as number | null | undefined, row.format)
  }

  const dataSource = RETRIEVAL_COMPARISON_ROWS.map((row) => {
    const live = resolveLive(row)
    return {
      key: row.key,
      metric: row.metric,
      hint: row.hint,
      phase0: row.phase0,
      phase2: row.phase2,
      phase3: row.phase3,
      live,
      delta: row.format === 'decimal' && live !== '—' ? calcDeltaVsP0(row.phase0, live) : '—',
    }
  })

  const columns = [
    {
      title: '指标',
      dataIndex: 'metric',
      key: 'metric',
      width: 200,
      render: (text: string, row: { hint?: string }) => (
        <span>
          {text}
          {row.hint && (
            <Typography.Text type="secondary" style={{ display: 'block', fontSize: 11 }}>
              {row.hint}
            </Typography.Text>
          )}
        </span>
      ),
    },
    {
      title: PHASE_LABELS.phase0,
      dataIndex: 'phase0',
      key: 'phase0',
      align: 'center' as const,
      width: 110,
    },
    {
      title: PHASE_LABELS.phase2,
      dataIndex: 'phase2',
      key: 'phase2',
      align: 'center' as const,
      width: 110,
    },
    {
      title: PHASE_LABELS.phase3,
      dataIndex: 'phase3',
      key: 'phase3',
      align: 'center' as const,
      width: 110,
      render: (v: string) => <Typography.Text strong>{v}</Typography.Text>,
    },
    {
      title: '当前报告',
      dataIndex: 'live',
      key: 'live',
      align: 'center' as const,
      width: 110,
      render: (v: string) => (
        <Typography.Text style={{ color: 'var(--accent-cyan, #00d4ff)' }} strong>
          {v}
        </Typography.Text>
      ),
    },
    {
      title: '相对 P0',
      dataIndex: 'delta',
      key: 'delta',
      align: 'center' as const,
      width: 90,
      render: (v: string) => {
        if (v === '—') return v
        const up = v.startsWith('+')
        return <Tag color={up ? 'success' : 'warning'}>{v}</Tag>
      },
    },
  ]

  const multihopColumns = [
    { title: '检索模式', dataIndex: 'mode', key: 'mode' },
    {
      title: 'Context Recall',
      dataIndex: 'recall',
      key: 'recall',
      align: 'center' as const,
      width: 120,
    },
    { title: '相对纯向量', dataIndex: 'delta', key: 'delta', align: 'center' as const, width: 100 },
  ]

  return (
    <HudPanel style={{ marginTop: 24 }}>
      <h3 className="chart-panel__title" style={{ marginBottom: 16 }}>
        检索能力演进对比（只读）
      </h3>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        评测集：{EVAL_COMPARISON_META.sampleSet}
        {' · '}
        阶段快照更新：{EVAL_COMPARISON_META.updatedAt}
        {report?.generated_at && (
          <>
            {' · '}
            当前报告生成：{formatDateTime(report.generated_at)}
          </>
        )}
      </Typography.Paragraph>
      <Typography.Paragraph
        type="secondary"
        style={{ fontSize: 12, marginTop: -8, marginBottom: 16 }}
      >
        {EVAL_COMPARISON_META.sourceNote}
      </Typography.Paragraph>

      <Table
        columns={columns}
        dataSource={dataSource}
        pagination={false}
        size="small"
        bordered
        style={{ marginBottom: 24 }}
      />

      <Typography.Title level={5} style={{ marginBottom: 12, color: 'var(--text-secondary)' }}>
        多跳 / 关系型（20 条 multi_hop）
      </Typography.Title>
      <Table
        columns={multihopColumns}
        dataSource={MULTIHOP_COMPARISON_ROWS}
        pagination={false}
        size="small"
        bordered
      />
    </HudPanel>
  )
}
