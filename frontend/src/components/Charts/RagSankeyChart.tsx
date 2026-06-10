/**
 * RAG 知识链路桑基图（ECharts）
 * 问题 → chunk → 回答 的流量可视化
 */
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import type { SankeyLink, SankeyNode } from '../../api/stats'
import ChartFillArea from './ChartFillArea'
import ResponsiveChart from './ResponsiveChart'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface RagSankeyChartProps {
  nodes: SankeyNode[]
  links: SankeyLink[]
  fill?: boolean
}

function sanitizeSankey(nodes: SankeyNode[], links: SankeyLink[]) {
  const nameSet = new Set(nodes.map((n) => n.name))
  const validLinks = links.filter(
    (l) => l.value > 0 && nameSet.has(l.source) && nameSet.has(l.target) && l.source !== l.target,
  )
  const used = new Set<string>()
  for (const l of validLinks) {
    used.add(l.source)
    used.add(l.target)
  }
  const validNodes = nodes.filter((n) => used.has(n.name))
  return { nodes: validNodes, links: validLinks }
}

const emptyBodyStyle: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--text-muted)',
  fontFamily: 'var(--font-mono)',
  fontSize: 13,
  textAlign: 'center',
  padding: '0 12px',
}

/** RAG 引用桑基图：q: 问题节点、c: chunk、其他为聚合节点 */
export default function RagSankeyChart({ nodes, links, fill = false }: RagSankeyChartProps) {
  const graph = useMemo(() => sanitizeSankey(nodes ?? [], links ?? []), [nodes, links])
  const panelClass = `chart-panel${fill ? ' chart-panel--fill' : ''}`

  if (graph.nodes.length === 0 || graph.links.length === 0) {
    return (
      <HudPanel className={panelClass}>
        <h3 className="chart-panel__title">RAG 知识链路（桑基图）</h3>
        <p style={fill ? emptyBodyStyle : { ...emptyBodyStyle, padding: '40px 0' }}>
          暂无对话引用数据，请先进行 AI 对话以生成引用链路
        </p>
      </HudPanel>
    )
  }

  const labelMap = Object.fromEntries(graph.nodes.map((n) => [n.name, n.label]))

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
        left: '2%',
        right: '8%',
        top: 8,
        bottom: 8,
        data: graph.nodes.map((n) => ({
          name: n.name,
          itemStyle: {
            color: n.name.startsWith('q:')
              ? '#00d4ff'
              : n.name.startsWith('c:')
                ? '#ff6b35'
                : '#10b981',
          },
        })),
        links: graph.links.map((l) => ({
          source: l.source,
          target: l.target,
          value: l.value,
        })),
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.4 },
        label: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (params) => labelMap[params.name] ?? params.name,
        },
      },
    ],
  }

  const chart = (h: number) => <ResponsiveChart option={option} height={h} notMerge lazyUpdate />

  return (
    <HudPanel className={panelClass}>
      <h3 className="chart-panel__title">RAG 知识链路（桑基图）</h3>
      {fill ? <ChartFillArea minHeight={120}>{chart}</ChartFillArea> : chart(360)}
    </HudPanel>
  )
}
