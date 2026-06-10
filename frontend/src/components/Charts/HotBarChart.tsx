/**
 * 知识热度 TOP 横向柱状图（ECharts）
 * 单库热门 chunk 命中次数排行
 * 主要导出：默认 HotBarChart 组件
 */
import type { EChartsOption } from 'echarts'
import ChartFillArea from './ChartFillArea'
import ResponsiveChart from './ResponsiveChart'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface HotBarChartProps {
  items: { content: string; hit_count: number }[]
  fill?: boolean
}

function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function buildOption(
  items: { content: string; hit_count: number }[],
  height: number,
): EChartsOption {
  const count = Math.max(items.length, 1)
  const slot = height / count
  const barWidth = Math.max(5, Math.min(10, Math.floor(slot * 0.42)))

  return {
    backgroundColor: 'transparent',
    grid: { left: 4, right: 12, top: 6, bottom: 6, containLabel: true },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.08)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: 9 },
    },
    yAxis: {
      type: 'category',
      data: items.map((_, i) => `#${i + 1}`).reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#94a3b8', fontFamily: 'JetBrains Mono', fontSize: 10 },
    },
    series: [
      {
        type: 'bar',
        data: items.map((it) => it.hit_count).reverse(),
        barWidth,
        barCategoryGap: '35%',
        itemStyle: {
          borderRadius: [0, 3, 3, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#00d4ff' },
              { offset: 1, color: '#ff6b35' },
            ],
          },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      confine: true,
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      extraCssText:
        'max-width:min(280px, 90vw); white-space:normal; word-break:break-word; overflow-wrap:break-word; line-height:1.45;',
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params
        const idx = items.length - 1 - (p.dataIndex ?? 0)
        const item = items[idx]
        if (!item) return ''
        const text = escapeHtml(item.content.trim())
        const preview = text.length > 120 ? `${text.slice(0, 120)}…` : text
        return `<div style="max-width:260px;white-space:normal;word-break:break-word;overflow-wrap:break-word;">${preview}<br/><b>${item.hit_count} 次命中</b></div>`
      },
    },
  }
}

/** 单库 TOP 热知识横向条形图，tooltip 展示内容摘要 */
export default function HotBarChart({ items, fill = false }: HotBarChartProps) {
  const chart = (h: number) => <ResponsiveChart option={buildOption(items, h)} height={h} />

  return (
    <HudPanel hot className={`chart-panel${fill ? ' chart-panel--fill' : ''}`}>
      <h3 className="chart-panel__title">知识热度 TOP</h3>
      {fill ? <ChartFillArea minHeight={100}>{chart}</ChartFillArea> : chart(280)}
    </HudPanel>
  )
}
