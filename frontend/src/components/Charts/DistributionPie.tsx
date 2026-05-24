import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface DistributionPieProps {
  data: { name: string; doc_count: number; chunk_count: number }[]
}

const COLORS = ['#00d4ff', '#33ddff', '#ff6b35', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b']

export default function DistributionPie({ data }: DistributionPieProps) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    color: COLORS,
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
    },
    legend: {
      orient: 'vertical',
      right: 8,
      top: 'center',
      textStyle: { color: '#94a3b8', fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        data: data.map((d) => ({ name: d.name, value: d.doc_count })),
        label: { show: false },
        itemStyle: { borderColor: '#0a0e17', borderWidth: 2 },
      },
    ],
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">知识库文档分布</h3>
      <ReactECharts option={option} style={{ height: 280 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
