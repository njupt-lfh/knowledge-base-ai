import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface HotBarChartProps {
  items: { content: string; hit_count: number }[]
}

export default function HotBarChart({ items }: HotBarChartProps) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 16, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.08)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono' },
    },
    yAxis: {
      type: 'category',
      data: items.map((_, i) => `#${i + 1}`).reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#94a3b8', fontFamily: 'JetBrains Mono' },
    },
    series: [
      {
        type: 'bar',
        data: items.map((it) => it.hit_count).reverse(),
        barWidth: 14,
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
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
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params
        const idx = items.length - 1 - (p.dataIndex ?? 0)
        const item = items[idx]
        if (!item) return ''
        return `<div style="max-width:240px">${item.content.slice(0, 60)}...<br/><b>${item.hit_count} 次命中</b></div>`
      },
    },
  }

  return (
    <HudPanel hot className="chart-panel">
      <h3 className="chart-panel__title">知识热度 TOP</h3>
      <ReactECharts option={option} style={{ height: 280 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
