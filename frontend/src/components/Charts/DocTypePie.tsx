/**
 * 单库文档类型占比环形图（ECharts）
 * 按 PDF / Markdown / TXT 等类型展示文档数量占比
 */
import type { EChartsOption } from 'echarts'
import type { DocTypeItem } from '../../api/stats'
import ChartFillArea from './ChartFillArea'
import ResponsiveChart from './ResponsiveChart'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface DocTypePieProps {
  data: DocTypeItem[]
  chartHeight?: number
  fill?: boolean
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

/** 单库文档类型数量占比饼图 */
export default function DocTypePie({ data, chartHeight = 300, fill = false }: DocTypePieProps) {
  const total = data.reduce((s, d) => s + d.count, 0)

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
        const pct = ((params.percent as number) ?? 0).toFixed(1)
        return `<b>${item.name}</b><br/>${item.count} 篇（${pct}%）`
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
        return item ? `${name}（${item.count}）` : name
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['35%', '50%'],
        data: data.map((d) => ({ name: d.name, value: d.count })),
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

  const chart = (h: number) => <ResponsiveChart option={option} height={h} />

  return (
    <HudPanel className={`chart-panel${fill ? ' chart-panel--fill' : ''}`}>
      <h3 className="chart-panel__title">文档类型分布（{total} 篇）</h3>
      {total === 0 ? (
        <p
          style={{
            color: 'var(--text-muted)',
            fontSize: 13,
            textAlign: 'center',
            margin: 'auto 0',
          }}
        >
          该知识库暂无文档
        </p>
      ) : fill ? (
        <ChartFillArea>{chart}</ChartFillArea>
      ) : (
        chart(chartHeight)
      )}
    </HudPanel>
  )
}
