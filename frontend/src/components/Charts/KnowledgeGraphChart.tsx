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
    animationDuration: 2000,
    animationEasingUpdate: 'quinticInOut',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        if (params.dataType === 'edge' && params.data) {
          return `${params.data.source}<br/>—[<b>${params.data.predicate}</b>]→<br/>${params.data.target}`
        }
        return params.data?.name ?? ''
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        force: {
          repulsion: 150,
          edgeLength: [80, 200],
          gravity: 0.06,
          friction: 0.6,
        },
        data: nodes.map((n) => ({
          id: n.id,
          name: n.name,
          symbolSize: Math.min(42, 16 + n.name.length * 1.5),
          itemStyle: {
            color: '#00d4ff',
            borderColor: 'rgba(0,212,255,0.7)',
            borderWidth: 2,
            shadowBlur: 12,
            shadowColor: 'rgba(0,212,255,0.4)',
          },
          label: { show: true, color: '#cbd5e1', fontSize: 10, distance: 4 },
          emphasis: {
            itemStyle: { color: '#ff6b35', borderColor: '#ff6b35', shadowBlur: 20 },
            label: { fontSize: 13, fontWeight: 'bold' },
          },
        })),
        links: edges.map((e) => ({
          source: e.source,
          target: e.target,
          lineStyle: {
            color: 'rgba(255,107,53,0.5)',
            curveness: 0.2,
            width: 1.2,
            opacity: 0.7,
          },
          label: { show: true, formatter: e.predicate, color: '#64748b', fontSize: 9 },
          emphasis: { lineStyle: { color: '#ff6b35', width: 3, opacity: 1 } },
        })),
        zoom: 1.2,
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 4 },
          itemStyle: { shadowBlur: 30 },
        },
      },
    ],
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">
        知识图谱（力导向 · {relationCount} 条关系 · {nodes.length} 实体）
      </h3>
      <ReactECharts
        option={option}
        style={{ height: 440 }}
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
