/**
 * 知识库文档分布环形图（ECharts）
 * 按各库文档数占比展示
 * 主要导出：默认 DistributionPie 组件
 */
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface DistributionPieProps {
  data: { name: string; doc_count: number; chunk_count: number }[]
}

const COLORS = [
  '#00d4ff',
  '#33ddff',
  '#ff6b35',
  '#10b981',
  '#f59e0b',
  '#8b5cf6',
  '#ec4899',
  '#64748b',
]

/** 全局知识库文档数量占比饼图 */
export default function DistributionPie({ data }: DistributionPieProps) {
  const total = data.reduce((s, d) => s + d.doc_count, 0)

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    color: COLORS,
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        const item = data[params.dataIndex]
        if (!item) return ''
        const pct = ((item.doc_count / total) * 100).toFixed(1)
        return `<b>${item.name}</b><br/>文档 ${item.doc_count} 个（${pct}%）<br/>知识块 ${item.chunk_count} 个`
      },
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 8,
      top: 'center',
      textStyle: { color: '#94a3b8', fontSize: 11 },
      formatter: (name: string) => {
        const item = data.find((d) => d.name === name)
        return item ? `${name}（${item.doc_count}）` : name
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['35%', '50%'],
        data: data.map((d) => ({ name: d.name, value: d.doc_count })),
        label: {
          show: true,
          position: 'outside',
          formatter: ({ percent }: any) => `${(percent as number).toFixed(0)}%`,
          color: '#94a3b8',
          fontSize: 10,
        },
        labelLine: { lineStyle: { color: 'rgba(148,163,184,0.3)' } },
        emphasis: {
          scaleSize: 12,
          focus: 'self',
          itemStyle: {
            shadowBlur: 20,
            shadowColor: 'rgba(0,212,255,0.4)',
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: { fontSize: 14, fontWeight: 'bold', color: '#e2e8f0' },
        },
        itemStyle: { borderColor: '#0a0e17', borderWidth: 2, borderRadius: 4 },
      },
    ],
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">知识库文档分布（{total} 篇）</h3>
      <ReactECharts option={option} style={{ height: 300 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
