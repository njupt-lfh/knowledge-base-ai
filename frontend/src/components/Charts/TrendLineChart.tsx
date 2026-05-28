import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import 'echarts-gl'
import type { TrendPoint } from '../../api/stats'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface TrendLineChartProps {
  points: TrendPoint[]
}

export default function TrendLineChart({ points }: TrendLineChartProps) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
    },
    xAxis3D: {
      type: 'category',
      data: points.map((p) => p.date.slice(5)),
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: 10 },
    },
    yAxis3D: { type: 'value', axisLabel: { show: false }, splitLine: { show: false } },
    zAxis3D: {
      type: 'value',
      name: '命中',
      nameTextStyle: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: 10 },
    },
    grid3D: {
      boxWidth: 100, boxDepth: 24, boxHeight: 80,
      viewControl: { alpha: 28, beta: 45, distance: 140, autoRotate: true, autoRotateSpeed: 1.5 },
      light: { main: { intensity: 1.0 }, ambient: { intensity: 0.5 } },
    },
    series: [
      {
        type: 'bar3D',
        data: points.map((p, i) => ({ value: [i, 0, p.hits] })),
        shading: 'realistic', barSize: 0.5,
        itemStyle: { color: '#00d4ff', opacity: 0.8 },
        emphasis: { itemStyle: { opacity: 1, color: '#ff6b35' } },
      },
      {
        type: 'line3D',
        data: points.map((p, i) => [i, 0, p.hits]),
        lineStyle: { color: '#ff6b35', width: 3 },
      },
    ],
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">RAG 引用趋势（7日 · 3D）</h3>
      <ReactECharts option={option} style={{ height: 340 }} opts={{ renderer: 'webgl' }} />
    </HudPanel>
  )
}
