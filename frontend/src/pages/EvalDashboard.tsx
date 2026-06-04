/**
 * RAG 评测基线仪表盘
 * 对比 Phase 0 与当前基线报告，雷达图与 KPI 卡片
 * 主要导出：默认 EvalDashboard 页面组件；内部 MetricCard、RadarChart、PhaseChangeTable
 */
import { useEffect, useState } from 'react'

import {
  Card,
  Col,
  Row,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
  Space,
  Alert,
  Tabs,
} from 'antd'
import {
  CheckCircleOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
  BugOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { evalApi, getReportSampleCount, type EvalBaselineReport, type EvalTrendPoint } from '../api/eval'
import request from '../api/request'
import HudPanel from '../components/common/HudPanel'
import { formatDateTime } from '../utils/format'

const BOTTLENECK_LABEL: Record<string, string> = {
  retrieval: '检索召回',
  retrieval_baseline_only: '检索专项',
  both: '检索与生成',
  generation: '生成质量',
  balanced: '整体均衡',
}

/* ───── 对比小卡片 ───── */
/** 单指标 KPI 卡片，相对 Phase 0 显示涨跌百分比 */
function MetricCard({
  label,
  value,
  baseline,
  unit: _unit,
  lowerIsBetter,
}: {
  label: string
  value: number | null
  baseline: number | null
  unit?: string
  lowerIsBetter?: boolean
}) {
  const cur = value ?? 0
  const base = baseline ?? 0
  const diff = base ? ((cur - base) / base) * 100 : 0
  const improved = lowerIsBetter ? diff < 0 : diff > 0
  const neutral = Math.abs(diff) < 2
  const color = neutral ? '#f59e0b' : improved ? '#10b981' : '#ef4444'
  const icon = neutral ? <MinusOutlined /> : improved ? <ArrowUpOutlined /> : <ArrowDownOutlined />

  return (
    <Card
      size="small"
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-subtle)',
        height: '100%',
      }}
    >
      <Statistic
        title={label}
        value={
          value != null ? (value < 1 ? (value * 100).toFixed(1) + '%' : value.toFixed(2)) : '—'
        }
        valueStyle={{
          color: 'var(--accent-cyan, #00d4ff)',
          fontSize: 26,
          fontFamily: 'var(--font-mono)',
        }}
        suffix={
          base ? (
            <span style={{ fontSize: 13, color }}>
              {icon} {Math.abs(diff).toFixed(0)}%
            </span>
          ) : undefined
        }
      />
      <Typography.Text type="secondary" style={{ fontSize: 11 }}>
        Phase 0:{' '}
        {baseline != null
          ? baseline < 1
            ? (baseline * 100).toFixed(1) + '%'
            : baseline.toFixed(3)
          : '—'}
      </Typography.Text>
    </Card>
  )
}

/* ───── 雷达图 ───── */
/** 六维能力雷达：Phase 0 虚线 vs 当前实线 */
function RadarChart({
  metrics,
}: {
  metrics: { label: string; p0: number | null; now: number | null }[]
}) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    legend: { data: ['Phase 0', '当前'], textStyle: { color: '#94a3b8' }, bottom: 0 },
    radar: {
      center: ['50%', '50%'],
      radius: '65%',
      indicator: metrics.map((m) => ({ name: m.label, max: 1 })),
      axisName: { color: '#94a3b8', fontSize: 11 },
      splitArea: { areaStyle: { color: ['rgba(0,212,255,0.02)', 'transparent'] } },
    },
    series: [
      {
        type: 'radar',
        name: 'Phase 0',
        data: [{ value: metrics.map((m) => m.p0 ?? 0), name: 'Phase 0' }],
        lineStyle: { color: '#64748b', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#64748b' },
        areaStyle: { opacity: 0.05 },
        symbol: 'none',
      },
      {
        type: 'radar',
        name: '当前',
        data: [{ value: metrics.map((m) => m.now ?? 0), name: '当前' }],
        lineStyle: { color: '#00d4ff', width: 2 },
        itemStyle: { color: '#00d4ff' },
        areaStyle: { color: 'rgba(0,212,255,0.15)' },
        symbol: 'circle',
        symbolSize: 4,
      },
    ],
  }
  return <ReactECharts option={option} style={{ height: 320 }} opts={{ renderer: 'canvas' }} />
}

/** 分维度指标块（题型 / 知识库） */
function DimensionMetricsTable({
  data,
  nameKey,
}: {
  data: Record<string, Record<string, unknown>> | undefined
  nameKey?: 'kb_name'
}) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <Typography.Text type="secondary">
        暂无分维度数据（请重新运行 run_rag_eval.py）
      </Typography.Text>
    )
  }

  const rows = Object.entries(data).map(([key, m]) => ({
    key,
    name: nameKey ? String(m[nameKey] ?? key) : key,
    sample_count: m.sample_count,
    cp: m.context_precision_chunk ?? m.context_precision_mean,
    cr: m.context_recall_chunk ?? m.context_recall_mean,
    mrr: m.mrr_mean,
    ndcg: m.ndcg_at_5_mean,
    hit: m.retrieval_hit_rate,
    reject: m.negative_reject_rate,
    faith: m.faithfulness_mean,
    relev: m.answer_relevancy_mean,
  }))

  const pct = (v: unknown) =>
    typeof v === 'number' ? (v < 1 ? (v * 100).toFixed(1) + '%' : v.toFixed(3)) : '—'

  return (
    <Table
      size="small"
      pagination={false}
      dataSource={rows}
      columns={[
        { title: nameKey ? '知识库' : '题型', dataIndex: 'name', key: 'name' },
        { title: '样本', dataIndex: 'sample_count', key: 'n', width: 60 },
        { title: 'CP-chunk', dataIndex: 'cp', key: 'cp', render: pct },
        { title: 'CR-chunk', dataIndex: 'cr', key: 'cr', render: pct },
        { title: 'MRR', dataIndex: 'mrr', key: 'mrr', render: pct },
        { title: 'NDCG@5', dataIndex: 'ndcg', key: 'ndcg', render: pct },
        { title: '命中率', dataIndex: 'hit', key: 'hit', render: pct },
        { title: '拒答率', dataIndex: 'reject', key: 'reject', render: pct },
      ]}
    />
  )
}

function trendPointTime(p: EvalTrendPoint): number {
  if (!p.created_at) return 0
  const t = new Date(/[zZ]|[+-]\d{2}:\d{2}$/.test(p.created_at) ? p.created_at : `${p.created_at}Z`).getTime()
  return Number.isNaN(t) ? 0 : t
}

/** 按运行时间升序，与 KPI 基线同一 dataset 版本 */
function sortTrendPoints(points: EvalTrendPoint[]): EvalTrendPoint[] {
  return [...points].sort((a, b) => trendPointTime(a) - trendPointTime(b))
}

/** 评测历史趋势折线图（DB eval_runs） */
function EvalTrendChart({
  points,
  title,
}: {
  points: EvalTrendPoint[]
  title: string
}) {
  if (!points.length) {
    return (
      <Typography.Text type="secondary">
        暂无历史运行记录（运行 run_rag_eval.py 后会自动写入 DB）
      </Typography.Text>
    )
  }
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    title: { text: title, left: 'center', textStyle: { color: '#94a3b8', fontSize: 13 } },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const items = Array.isArray(params) ? params : [params]
        const idx = (items[0] as { dataIndex?: number })?.dataIndex ?? 0
        const p = points[idx]
        const pct =
          p?.value != null && !Number.isNaN(p.value) ? `${(p.value * 100).toFixed(1)}%` : '—'
        const when = p?.created_at ? formatDateTime(p.created_at) : '—'
        const mode = p?.eval_mode ?? ''
        return `${when}<br/>${title}: <b>${pct}</b>${mode ? `<br/>模式: ${mode}` : ''}`
      },
    },
    grid: { left: 48, right: 24, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: points.map((p) => (p.created_at ? formatDateTime(p.created_at) : p.run_id.slice(0, 8))),
      axisLabel: { color: '#64748b', fontSize: 10, rotate: 30 },
    },
    yAxis: {
      type: 'value',
      max: 1,
      axisLabel: { color: '#64748b', formatter: (v: number) => `${(v * 100).toFixed(1)}%` },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: points.map((p) => p.value ?? 0),
        lineStyle: { color: '#00d4ff', width: 2 },
        itemStyle: { color: '#00d4ff' },
        areaStyle: { color: 'rgba(0,212,255,0.08)' },
      },
    ],
  }
  return <ReactECharts option={option} style={{ height: 280 }} opts={{ renderer: 'canvas' }} />
}

/** RAG 评测基线可视化页 */
export default function EvalDashboard() {
  const [report, setReport] = useState<EvalBaselineReport | null>(null)
  const [phase0, setPhase0] = useState<EvalBaselineReport | null>(null)
  const [cpTrend, setCpTrend] = useState<EvalTrendPoint[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [baselineRes, phase0Res] = await Promise.allSettled([
          evalApi.getBaseline(),
          request
            .get('/api/eval/baseline-phase0')
            .then((r) => r?.data)
            .catch(() => null),
        ])
        if (cancelled) return
        const baseline = baselineRes.status === 'fulfilled' ? baselineRes.value?.data : null
        if (baseline) setReport(baseline)
        if (phase0Res.status === 'fulfilled' && phase0Res.value) setPhase0(phase0Res.value)

        const datasetVer =
          (baseline as EvalBaselineReport | null)?.dataset_version ??
          baseline?.config?.dataset ??
          'v1'
        const trendRes = await evalApi.getTrend('context_precision_chunk', datasetVer)
        if (!cancelled) {
          setCpTrend(sortTrendPoints(trendRes?.data?.points ?? []))
        }
      } catch {
        if (!cancelled) message.error('未找到基线报告')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const agg = report?.aggregate ?? {}
  const p0agg = phase0?.aggregate ?? {}
  const sampleCount = report ? getReportSampleCount(report) : undefined
  const datasetVer = (report as { dataset_version?: string })?.dataset_version ?? 'v1'
  const evalMode =
    (report?.config?.eval_mode ?? report?.config?.retrieval_only) ? 'retrieval_only' : 'full'
  const bottleneck = report?.diagnosis?.primary_bottleneck

  // 从 Phase 0 aggregate 安全读取数值
  const p0 = (field: string): number | null => {
    const v = p0agg[field]
    return typeof v === 'number' && !Number.isNaN(v) ? v : null
  }

  // 雷达图六维指标映射
  const radarMetrics = [
    {
      label: '召回率',
      p0: p0('context_recall_mean'),
      now: agg.context_recall_mean as number | null,
    },
    {
      label: '精确率',
      p0: p0('context_precision_mean'),
      now: agg.context_precision_mean as number | null,
    },
    { label: '命中率', p0: p0('retrieval_hit_rate'), now: agg.retrieval_hit_rate as number | null },
    {
      label: '负例拒答',
      p0: p0('negative_reject_rate'),
      now: agg.negative_reject_rate as number | null,
    },
    {
      label: '忠实度',
      p0: p0('faithfulness_mean') ?? p0('ragas_faithfulness'),
      now: (agg.faithfulness_mean ?? (agg.ragas?.faithfulness as number | null)) as number | null,
    },
    {
      label: '相关性',
      p0: p0('answer_relevancy_mean') ?? p0('ragas_answer_relevancy'),
      now: (agg.answer_relevancy_mean ?? (agg.ragas?.answer_relevancy as number | null)) as
        | number
        | null,
    },
  ]

  return (
    <div>
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        {/* ─── 头部 ─── */}
        <HudPanel>
          <Row align="middle" justify="space-between">
            <Col>
              <Space>
                <ExperimentOutlined
                  style={{ color: 'var(--accent-cyan, #00d4ff)', fontSize: 22 }}
                />
                <span style={{ color: '#e2e8f0', fontSize: 18, fontWeight: 600 }}>
                  RAG 评测基线
                </span>
                {report && (
                  <Tag color="cyan">
                    {datasetVer} · {sampleCount ?? '—'} 样本
                    {evalMode === 'retrieval_only' ? ' · 检索专项' : ''}
                  </Tag>
                )}
              </Space>
            </Col>
            <Col>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {report?.generated_at ? `生成: ${formatDateTime(report.generated_at)}` : ''}
                {sampleCount ? ` · 样本: ${sampleCount}` : ''}
              </Typography.Text>
            </Col>
          </Row>
        </HudPanel>

        {loading && <Typography.Text>加载中...</Typography.Text>}

        {report && (
          <>
            {/* ─── 诊断条 ─── */}
            {bottleneck && (
              <Alert
                type={
                  bottleneck === 'retrieval' || bottleneck === 'retrieval_baseline_only'
                    ? 'warning'
                    : 'info'
                }
                message={`诊断结论：主要瓶颈在 ${BOTTLENECK_LABEL[bottleneck] ?? bottleneck}`}
                description={report?.diagnosis?.recommendation}
                icon={bottleneck === 'retrieval' ? <BugOutlined /> : <CheckCircleOutlined />}
                showIcon
                style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-subtle)' }}
              />
            )}

            {/* ─── KPI 卡片行 ─── */}
            <Row gutter={16}>
              <Col span={8}>
                <MetricCard
                  label="上下文召回"
                  value={agg.context_recall_mean as number | null}
                  baseline={p0('context_recall_mean')}
                />
              </Col>
              <Col span={8}>
                <MetricCard
                  label="CP-chunk（chunk级精确率）"
                  value={
                    (agg.context_precision_chunk as number | null) ??
                    (agg.context_precision_mean as number | null)
                  }
                  baseline={
                    (p0('context_precision_chunk') ?? p0('context_precision_mean')) as number | null
                  }
                  lowerIsBetter={false}
                />
              </Col>
              <Col span={8}>
                <MetricCard
                  label="检索命中率"
                  value={agg.retrieval_hit_rate as number | null}
                  baseline={p0('retrieval_hit_rate')}
                />
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={8}>
                <MetricCard
                  label="负例拒答"
                  value={agg.negative_reject_rate as number | null}
                  baseline={p0('negative_reject_rate')}
                />
              </Col>
              <Col span={8}>
                <MetricCard
                  label="答案忠实度"
                  value={
                    (agg.faithfulness_mean ?? (agg.ragas?.faithfulness as number | null)) as
                      | number
                      | null
                  }
                  baseline={(p0('faithfulness_mean') ?? p0('ragas_faithfulness')) as number | null}
                />
              </Col>
              <Col span={8}>
                <MetricCard
                  label="答案相关性"
                  value={
                    (agg.answer_relevancy_mean ??
                      (agg.ragas?.answer_relevancy as number | null)) as number | null
                  }
                  baseline={
                    (p0('answer_relevancy_mean') ?? p0('ragas_answer_relevancy')) as number | null
                  }
                />
              </Col>
            </Row>
            {(report?.by_question_type || report?.by_kb) && (
              <HudPanel>
                <Tabs
                  defaultActiveKey="type"
                  items={[
                    {
                      key: 'type',
                      label: '按题型',
                      children: <DimensionMetricsTable data={report?.by_question_type} />,
                    },
                    {
                      key: 'kb',
                      label: '按知识库',
                      children: <DimensionMetricsTable data={report?.by_kb} nameKey="kb_name" />,
                    },
                  ]}
                />
              </HudPanel>
            )}

            <HudPanel>
              <h3 className="chart-panel__title">历史趋势（CP-chunk）</h3>
              <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                数据来自 eval_runs（与上方 KPI 同数据集 {datasetVer}）；运行 run_rag_eval.py 后自动写入，时间为 UTC 转本地显示。
              </Typography.Text>
              <EvalTrendChart points={cpTrend} title="context_precision_chunk 历次运行" />
            </HudPanel>

            {/* ─── 雷达图 + 检索对比表 ─── */}
            <Row gutter={16}>
              <Col span={12}>
                <HudPanel style={{ minHeight: 380 }}>
                  <h3 className="chart-panel__title">六维能力雷达图</h3>
                  {phase0 ? (
                    <RadarChart metrics={radarMetrics} />
                  ) : (
                    <Typography.Text type="secondary">
                      缺少 Phase 0
                      基线备份（eval_baseline_report_phase0.json），无法生成对比雷达图。
                    </Typography.Text>
                  )}
                </HudPanel>
              </Col>
              <Col span={12}>
                <HudPanel style={{ minHeight: 380 }}>
                  <h3 className="chart-panel__title">Phase 0 → 当前 变化</h3>
                  <PhaseChangeTable agg={agg} p0agg={p0agg} />
                </HudPanel>
              </Col>
            </Row>

            {/* ─── RAGAS 生成质量（若存在） ─── */}
            {agg.ragas && Object.keys(agg.ragas).length > 0 && (
              <HudPanel>
                <h3 className="chart-panel__title">RAGAS 生成质量评测</h3>
                <Row gutter={16} style={{ marginTop: 12 }}>
                  {(
                    [
                      'faithfulness',
                      'answer_relevancy',
                      'context_precision',
                      'context_recall',
                    ] as const
                  ).map((k) => (
                    <Col span={6} key={k}>
                      <Card
                        size="small"
                        style={{
                          background: 'var(--bg-elevated)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <Statistic
                          title={
                            k === 'faithfulness'
                              ? '答案忠实度 (FA)'
                              : k === 'answer_relevancy'
                                ? '答案相关性 (AR)'
                                : k === 'context_precision'
                                  ? 'CP-ragas（RAGAS加权精确率）'
                                  : 'CR-ragas（RAGAS召回）'
                          }
                          value={Number(agg.ragas?.[k] ?? 0)}
                          precision={4}
                          valueStyle={{
                            color: 'var(--accent-cyan, #00d4ff)',
                            fontSize: 22,
                            fontFamily: 'var(--font-mono)',
                          }}
                        />
                        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                          RAGAS 评分
                        </Typography.Text>
                      </Card>
                    </Col>
                  ))}
                </Row>
              </HudPanel>
            )}
          </>
        )}

        {!loading && !report && (
          <Alert
            type="warning"
            showIcon
            message="未找到基线报告"
            description="请运行 backend/scripts/run_rag_eval.py 生成评测基线。"
          />
        )}
      </Space>
    </div>
  )
}

/* ───── Phase 变化明细表 ───── */
/** Phase 0 → 当前各指标变化百分比表格 */
function PhaseChangeTable({
  agg,
  p0agg,
}: {
  agg: Record<string, unknown>
  p0agg: Record<string, unknown>
}) {
  const metrics = [
    { key: 'context_recall_mean', label: '上下文召回', goodUp: true },
    { key: 'context_precision_mean', label: '上下文精确', goodUp: true },
    { key: 'retrieval_hit_rate', label: '命中率', goodUp: true },
    { key: 'negative_reject_rate', label: '负例拒答', goodUp: true },
    { key: 'faithfulness_mean', label: '忠实度', goodUp: true },
    { key: 'answer_relevancy_mean', label: '答案相关性', goodUp: true },
  ]

  return (
    <Table
      size="small"
      pagination={false}
      dataSource={metrics
        .filter((m) => agg[m.key] != null)
        .map((m) => {
          const cur = Number(agg[m.key])
          const base = p0agg[m.key] != null ? Number(p0agg[m.key]) : null
          const diff = base != null && base !== 0 ? ((cur - base) / base) * 100 : 0
          const neutral = Math.abs(diff) < 3
          const improved = m.goodUp ? diff > 0 : diff < 0
          return {
            key: m.key,
            metric: m.label,
            p0: base != null ? (base < 1 ? (base * 100).toFixed(1) + '%' : base.toFixed(3)) : '—',
            now: cur < 1 ? (cur * 100).toFixed(1) + '%' : cur.toFixed(3),
            delta: base != null ? `${diff >= 0 ? '+' : ''}${diff.toFixed(0)}%` : '—',
            tag: base == null ? 'new' : neutral ? 'flat' : improved ? 'up' : 'down',
          }
        })}
      columns={[
        { title: '指标', dataIndex: 'metric', key: 'metric' },
        { title: 'Phase 0', dataIndex: 'p0', key: 'p0', align: 'center' as const },
        {
          title: '当前',
          dataIndex: 'now',
          key: 'now',
          align: 'center' as const,
          render: (v: string) => (
            <Typography.Text strong style={{ color: 'var(--accent-cyan, #00d4ff)' }}>
              {v}
            </Typography.Text>
          ),
        },
        {
          title: '变化',
          dataIndex: 'delta',
          key: 'delta',
          align: 'center' as const,
          render: (_: string, row: { delta: string; tag: string }) => {
            const colors: Record<string, string> = {
              up: 'success',
              down: 'error',
              flat: 'warning',
              new: 'processing',
            }
            return row.delta !== '—' ? (
              <Tag color={colors[row.tag] ?? 'default'}>{row.delta}</Tag>
            ) : (
              <>—</>
            )
          },
        },
      ]}
    />
  )
}
