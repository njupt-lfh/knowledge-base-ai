import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import 'echarts-gl'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface HotBarChartProps {
  items: { content: string; hit_count: number }[]
}

export default function HotBarChart({ items }: HotBarChartProps) {
  const data = items.map((it, i) => ({
    value: [i, 0, it.hit_count],
    name: it.content.slice(0, 40),
  }))

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.name}...<br/><b>${p.value?.[2] ?? 0} 次命中</b>`
      },
    },
    xAxis3D: {
      type: 'category',
      data: items.map((_, i) => `#${i + 1}`),
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
      axisLabel: { color: '#64748b', fontSize: 10 },
      nameTextStyle: { color: '#64748b' },
    },
    yAxis3D: {
      type: 'value',
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.1)' } },
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.05)' } },
      axisLabel: { show: false },
    },
    zAxis3D: {
      type: 'value',
      name: '命中次数',
      nameTextStyle: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(255,107,53,0.3)' } },
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.06)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: 10 },
    },
    grid3D: {
      boxWidth: Math.max(50, items.length * 18),
      boxDepth: 30,
      boxHeight: 80,
      viewControl: {
        alpha: 25,
        beta: 30,
        distance: 160,
        autoRotate: true,
        autoRotateSpeed: 2,
      },
      light: {
        main: { intensity: 1.2, shadow: true },
        ambient: { intensity: 0.4 },
      },
    },
    series: [
      {
        type: 'bar3D',
        data,
        shading: 'realistic',
        barSize: 0.6,
        itemStyle: {
          color: (params: any) => {
            const idx = params.dataIndex ?? 0
            const ratio = items.length > 1 ? idx / (items.length - 1) : 0.5
            const r = Math.round(0 + (255 - 0) * (1 - ratio))
            const g = Math.round(212 * (1 - ratio) + 107 * ratio)
            const b = Math.round(255 * (1 - ratio) + 53 * ratio)
            return `rgb(${r},${g},${b})`
          },
          opacity: 0.85,
        },
        emphasis: {
          itemStyle: { opacity: 1 },
          label: { show: true, formatter: (p: any) => `${p.value?.[2] ?? ''}`, color: '#fff' },
        },
      },
    ],
  }

  return (
    <HudPanel hot className="chart-panel">
      <h3 className="chart-panel__title">知识热度 TOP · 3D</h3>
      <ReactECharts option={option} style={{ height: 340 }} opts={{ renderer: 'webgl' }} />
    </HudPanel>
  )
}
