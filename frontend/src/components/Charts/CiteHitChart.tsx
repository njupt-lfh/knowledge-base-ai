/**
 * 命中 vs 引用双柱对比图（ECharts）
 * 对比检索命中与对话实际引用次数
 * 主要导出：默认 CiteHitChart 组件
 */
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { CiteHitItem } from '../../api/stats'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface CiteHitChartProps {
  items: CiteHitItem[]
}

/** TOP chunk 的检索命中与对话引用并排柱状图 */
export default function CiteHitChart({ items }: CiteHitChartProps) {
  if (items.length === 0) {
    return (
      <HudPanel hot className="chart-panel">
        <h3 className="chart-panel__title">命中 vs 引用转化率</h3>
        <p
          style={{
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            padding: '40px 0',
          }}
        >
          暂无引用数据，请先进行 AI 对话以产生引用记录
        </p>
      </HudPanel>
    )
  }

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    legend: {
      data: ['检索命中', '对话引用'],
      textStyle: { color: '#94a3b8', fontSize: 11 },
      top: 0,
    },
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: items.map((i) => i.label),
      axisLabel: { color: '#64748b', fontSize: 10, rotate: items.length > 5 ? 25 : 0 },
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.2)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.08)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono' },
    },
    series: [
      {
        name: '检索命中',
        type: 'bar',
        data: items.map((i) => i.hit_count),
        itemStyle: { color: '#00d4ff', borderRadius: [4, 4, 0, 0] },
        barGap: '10%',
      },
      {
        name: '对话引用',
        type: 'bar',
        data: items.map((i) => i.cite_count),
        itemStyle: { color: '#ff6b35', borderRadius: [4, 4, 0, 0] },
      },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
    },
  }

  return (
    <HudPanel hot className="chart-panel">
      <h3 className="chart-panel__title">命中 vs 引用转化率</h3>
      <ReactECharts option={option} style={{ height: 280 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
