/**
 * RAG 评测基线仪表盘
 * 对比 Phase 0 与当前基线报告，雷达图与 KPI 卡片
 * 主要导出：默认 EvalDashboard 页面组件；内部 MetricCard、RadarChart、PhaseChangeTable
 */
import { useEffect, useState } from 'react'

import { Card, Col, Row, Statistic, Table, Tag, Typography, message, Space, Alert } from 'antd'
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
import { evalApi, getReportSampleCount, type EvalBaselineReport } from '../api/eval'
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

/* ───── 主页面 ───── */
/** RAG 评测基线可视化页 */
export default function EvalDashboard() {
  const [report, setReport] = useState<EvalBaselineReport | null>(null)
  const [phase0, setPhase0] = useState<EvalBaselineReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 并行加载当前基线与 Phase 0 备份（用于对比）
    Promise.allSettled([
      evalApi.getBaseline(),
      request
        .get('/api/eval/baseline-phase0')
        .then((r) => r?.data)
        .catch(() => null),
    ])
      .then(([r1, r2]) => {
        if (r1.status === 'fulfilled' && r1.value?.data) setReport(r1.value.data)
        if (r2.status === 'fulfilled' && r2.value) setPhase0(r2.value)
      })
      .catch(() => message.error('未找到基线报告'))
      .finally(() => setLoading(false))
  }, [])

  const agg = report?.aggregate ?? {}
  const p0agg = phase0?.aggregate ?? {}
  const sampleCount = report ? getReportSampleCount(report) : undefined
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
    <div style={{ padding: 24 }}>
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
                {report && <Tag color="cyan">100 样本 · 5 知识库</Tag>}
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
                  label="上下文精确"
                  value={agg.context_precision_mean as number | null}
                  baseline={p0('context_precision_mean')}
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
                              ? '答案忠实度'
                              : k === 'answer_relevancy'
                                ? '答案相关性'
                                : k === 'context_precision'
                                  ? '上下文精确率'
                                  : '上下文召回率'
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
