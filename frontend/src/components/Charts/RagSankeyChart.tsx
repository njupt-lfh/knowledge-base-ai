import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { SankeyLink, SankeyNode } from '../../api/stats'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface RagSankeyChartProps {
  nodes: SankeyNode[]
  links: SankeyLink[]
}

export default function RagSankeyChart({ nodes, links }: RagSankeyChartProps) {
  if (nodes.length === 0 || links.length === 0) {
    return (
      <HudPanel className="chart-panel">
        <h3 className="chart-panel__title">RAG 知识链路（桑基图）</h3>
        <p
          style={{
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            padding: '40px 0',
          }}
        >
          暂无对话引用数据，请先进行 AI 对话以生成引用链路
        </p>
      </HudPanel>
    )
  }

  const labelMap = Object.fromEntries(nodes.map((n) => [n.name, n.label]))

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params) => {
        const p = params as {
          dataType?: string
          name?: string
          data?: SankeyLink & { source?: string; target?: string }
        }
        if (p.dataType === 'edge' && p.data) {
          return `${labelMap[p.data.source ?? ''] ?? p.data.source} → ${labelMap[p.data.target ?? ''] ?? p.data.target}<br/>流量: ${p.data.value?.toFixed(2)}`
        }
        return labelMap[p.name ?? ''] ?? p.name ?? ''
      },
    },
    series: [
      {
        type: 'sankey',
        emphasis: { focus: 'adjacency' },
        nodeAlign: 'left',
        data: nodes.map((n) => ({
          name: n.name,
          itemStyle: {
            color: n.name.startsWith('q:')
              ? '#00d4ff'
              : n.name.startsWith('c:')
                ? '#ff6b35'
                : '#10b981',
          },
        })),
        links: links.map((l) => ({ source: l.source, target: l.target, value: l.value })),
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.4 },
        label: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (params) => labelMap[params.name] ?? params.name,
        },
      },
    ],
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">RAG 知识链路（桑基图）</h3>
      <ReactECharts option={option} style={{ height: 360 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
