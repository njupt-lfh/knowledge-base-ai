/**
 * 知识图谱力导向图（ECharts Graph）
 * 展示实体节点与关系边，支持拖拽与缩放
 * 主要导出：默认 KnowledgeGraphChart 组件（memo 优化）
 */
import { memo, useEffect, useRef, useState } from 'react'
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

/** 力导向布局的知识图谱，节点大小随实体名长度微调 */
function KnowledgeGraphChart({ nodes, edges, relationCount }: KnowledgeGraphChartProps) {
  const chartRef = useRef<InstanceType<typeof ReactECharts> | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [chartSize, setChartSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const syncSize = () => {
      const width = el.clientWidth
      const height = el.clientHeight
      if (width > 0 && height > 0) {
        setChartSize({ width, height })
        chartRef.current?.getEchartsInstance()?.resize()
      }
    }
    const ro = new ResizeObserver(syncSize)
    ro.observe(el)
    syncSize()
    return () => ro.disconnect()
  }, [])

  if (nodes.length === 0 || edges.length === 0) {
    return (
      <HudPanel className="chart-panel kb-graph-panel kb-graph-panel--empty">
        <h3 className="chart-panel__title">知识图谱（实体关系）</h3>
        <p className="kb-graph-panel__empty-text">
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
          predicate: e.predicate,
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
    <HudPanel className="chart-panel kb-graph-panel">
      <h3 className="chart-panel__title kb-graph-panel__title">
        知识图谱（力导向 · {relationCount} 条关系 · {nodes.length} 实体）
      </h3>
      <div ref={containerRef} className="kb-graph-chart">
        {chartSize.height > 0 && (
          <ReactECharts
            ref={chartRef}
            option={option}
            style={{ height: chartSize.height, width: chartSize.width }}
            opts={{ renderer: 'canvas' }}
            notMerge
            lazyUpdate
          />
        )}
      </div>
    </HudPanel>
  )
}

/** 节点/边数量不变时跳过重渲染，避免力导向布局抖动 */
export default memo(
  KnowledgeGraphChart,
  (prev, next) =>
    prev.relationCount === next.relationCount &&
    prev.nodes.length === next.nodes.length &&
    prev.edges.length === next.edges.length,
)
