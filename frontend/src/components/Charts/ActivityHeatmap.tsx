import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { ActivityPoint } from '../../api/stats'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

const DAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const HOURS = Array.from({ length: 24 }, (_, i) => `${i}`)

interface ActivityHeatmapProps {
  points: ActivityPoint[]
}

export default function ActivityHeatmap({ points }: ActivityHeatmapProps) {
  const data = points.map((p) => [p.hour, p.dow, p.count])
  const maxVal = Math.max(...points.map((p) => p.count), 1)

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    grid: { left: 48, right: 16, top: 16, bottom: 48 },
    xAxis: {
      type: 'category',
      data: HOURS,
      splitArea: { show: true },
      axisLabel: { color: '#64748b', fontSize: 10, interval: 3 },
    },
    yAxis: {
      type: 'category',
      data: DAYS,
      splitArea: { show: true },
      axisLabel: { color: '#94a3b8', fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: {
        color: ['#111827', '#0e4d66', '#00d4ff', '#ff6b35'],
      },
      textStyle: { color: '#94a3b8', fontSize: 10 },
    },
    series: [
      {
        type: 'heatmap',
        data,
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,212,255,0.4)' },
        },
      },
    ],
    tooltip: {
      position: 'top',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
      formatter: (params) => {
        const p = params as { data?: number[] }
        if (!p.data) return ''
        const [hour, dow, count] = p.data
        return `${DAYS[dow]} ${hour}:00<br/><b>${count} 条消息</b>`
      },
    },
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">活跃时段热力图（真实消息）</h3>
      <ReactECharts option={option} style={{ height: 300 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
