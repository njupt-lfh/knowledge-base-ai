import { memo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { GraphEdge, GraphNode } from '../../api/graph'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface KnowledgeGraphChartProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  relationCount: number
}

function KnowledgeGraphChart({ nodes, edges, relationCount }: KnowledgeGraphChartProps) {
  if (nodes.length === 0 || edges.length === 0) {
    return (
      <HudPanel className="chart-panel">
        <h3 className="chart-panel__title">知识图谱（实体关系）</h3>
        <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 13, padding: '40px 0' }}>
          暂无图谱数据。上传或录入含实体关系的文档后，系统会自动抽取三元组。
        </p>
      </HudPanel>
    )
  }

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params) => {
        const p = params as { dataType?: string; data?: GraphEdge & { name?: string; value?: number } }
        if (p.dataType === 'edge' && p.data) {
          return `${p.data.source} —[${p.data.predicate}]→ ${p.data.target}`
        }
        return p.data?.name ?? ''
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        force: { repulsion: 120, edgeLength: [60, 120], gravity: 0.08 },
        data: nodes.map((n) => ({
          id: n.id,
          name: n.name,
          symbolSize: Math.min(36, 14 + n.name.length),
          itemStyle: { color: '#00d4ff', borderColor: 'rgba(0,212,255,0.5)', borderWidth: 1 },
          label: { show: true, color: '#94a3b8', fontSize: 10 },
        })),
        links: edges.map((e) => ({
          source: e.source,
          target: e.target,
          lineStyle: { color: 'rgba(255,107,53,0.45)', curveness: 0.15 },
          label: { show: true, formatter: e.predicate, color: '#64748b', fontSize: 9 },
        })),
        emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
      },
    ],
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">
        知识图谱（力导向 · {relationCount} 条关系）
      </h3>
      <ReactECharts
        option={option}
        style={{ height: 420 }}
        opts={{ renderer: 'canvas' }}
        notMerge
        lazyUpdate
      />
    </HudPanel>
  )
}

export default memo(KnowledgeGraphChart, (prev, next) =>
  prev.relationCount === next.relationCount &&
  prev.nodes.length === next.nodes.length &&
  prev.edges.length === next.edges.length
)
