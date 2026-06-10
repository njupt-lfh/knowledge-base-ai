/**
 * 命中 vs 引用双柱对比图（ECharts）
 * 对比检索命中与对话实际引用次数
 * 主要导出：默认 CiteHitChart 组件
 */
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import type { CiteHitItem } from '../../api/stats'
import ChartFillArea from './ChartFillArea'
import ResponsiveChart from './ResponsiveChart'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface CiteHitChartProps {
  items: CiteHitItem[]
  fill?: boolean
}

function buildOption(items: CiteHitItem[], height: number): EChartsOption {
  const compact = height < 240
  const tight = height < 180

  return {
    backgroundColor: 'transparent',
    legend: {
      data: ['检索命中', '对话引用'],
      textStyle: { color: '#94a3b8', fontSize: tight ? 9 : compact ? 10 : 11 },
      top: 0,
      itemWidth: tight ? 10 : 14,
      itemHeight: tight ? 8 : 10,
    },
    grid: {
      left: 4,
      right: 8,
      top: tight ? 22 : compact ? 28 : 36,
      bottom: tight ? 4 : 8,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: items.map((i) => i.label),
      axisLabel: {
        color: '#64748b',
        fontSize: tight ? 8 : 9,
        rotate: items.length > 5 || compact ? 30 : 0,
        interval: 0,
      },
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.2)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.08)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: tight ? 9 : 10 },
    },
    series: [
      {
        name: '检索命中',
        type: 'bar',
        data: items.map((i) => i.hit_count),
        itemStyle: { color: '#00d4ff', borderRadius: [3, 3, 0, 0] },
        barGap: '8%',
        barMaxWidth: tight ? 10 : compact ? 14 : 20,
      },
      {
        name: '对话引用',
        type: 'bar',
        data: items.map((i) => i.cite_count),
        itemStyle: { color: '#ff6b35', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: tight ? 10 : compact ? 14 : 20,
      },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 11 },
    },
  }
}

/** TOP chunk 的检索命中与对话引用并排柱状图 */
export default function CiteHitChart({ items, fill = false }: CiteHitChartProps) {
  const defaultOption = useMemo(() => buildOption(items, 280), [items])

  if (items.length === 0) {
    return (
      <HudPanel hot className={`chart-panel${fill ? ' chart-panel--fill' : ''}`}>
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

  const chart = (h: number) => <ResponsiveChart option={buildOption(items, h)} height={h} />

  return (
    <HudPanel hot className={`chart-panel${fill ? ' chart-panel--fill' : ''}`}>
      <h3 className="chart-panel__title">命中 vs 引用转化率</h3>
      {fill ? (
        <ChartFillArea minHeight={120}>{chart}</ChartFillArea>
      ) : (
        <ResponsiveChart option={defaultOption} height={280} />
      )}
    </HudPanel>
  )
}
