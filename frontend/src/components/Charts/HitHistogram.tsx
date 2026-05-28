import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import 'echarts-gl'
import type { HitBucket } from '../../api/stats'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface HitHistogramProps {
  buckets: HitBucket[]
}

const COLORS = ['#64748b', '#00d4ff', '#33ddff', '#ff6b35']

export default function HitHistogram({ buckets }: HitHistogramProps) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.name}<br/><b>${p.value?.[2] ?? 0} 个知识块</b>`
      },
    },
    xAxis3D: {
      type: 'category', data: buckets.map((b) => b.label),
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.3)' } },
    },
    yAxis3D: { type: 'value', axisLabel: { show: false } },
    zAxis3D: {
      type: 'value', name: '数量',
      nameTextStyle: { color: '#64748b', fontSize: 11 },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: 10 },
    },
    grid3D: {
      boxWidth: 80, boxDepth: 30, boxHeight: 80,
      viewControl: { alpha: 25, beta: 40, distance: 120, autoRotate: true, autoRotateSpeed: 1.2 },
      light: { main: { intensity: 1.0 }, ambient: { intensity: 0.5 } },
    },
    series: [{
      type: 'bar3D',
      data: buckets.map((b, i) => ({ value: [i, 0, b.count] })),
      shading: 'realistic', barSize: 0.6,
      itemStyle: {
        color: (params: any) => COLORS[params.dataIndex as number] ?? '#00d4ff',
        opacity: 0.85,
      },
    }],
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">热度分布 · 3D</h3>
      <ReactECharts option={option} style={{ height: 300 }} opts={{ renderer: 'webgl' }} />
    </HudPanel>
  )
}
