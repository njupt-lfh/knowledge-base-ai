/**
 * 检索相似度雷达图（ECharts）
 * 检索测试页展示 Top-K 各条结果的 score 分布
 * 主要导出：默认 SearchRadarChart 组件
 */
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface SearchRadarChartProps {
  scores: number[]
  query?: string
}

/** 单次检索 Top-N 相似度雷达，max 固定为 1 */
export default function SearchRadarChart({ scores, query }: SearchRadarChartProps) {
  if (scores.length === 0) return null

  const indicators = scores.map((_, i) => ({
    name: `Top ${i + 1}`,
    max: 1,
  }))

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    radar: {
      indicator: indicators,
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.12)' } },
      splitArea: { areaStyle: { color: ['rgba(0,212,255,0.02)', 'rgba(0,212,255,0.06)'] } },
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.2)' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: scores,
            name: '相似度',
            areaStyle: { color: 'rgba(0,212,255,0.2)' },
            lineStyle: { color: '#00d4ff', width: 2 },
            itemStyle: { color: '#00d4ff' },
          },
        ],
      },
    ],
    tooltip: {
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
      formatter: (params) => {
        const p = params as { data?: { value?: number[] } }
        const vals = p.data?.value ?? []
        return vals.map((v, i) => `Top ${i + 1}: ${v.toFixed(4)}`).join('<br/>')
      },
    },
  }

  return (
    <HudPanel className="chart-panel" style={{ marginTop: 16 }}>
      <h3 className="chart-panel__title">
        向量相似度雷达 {query ? `· "${query.slice(0, 20)}${query.length > 20 ? '...' : ''}"` : ''}
      </h3>
      <ReactECharts option={option} style={{ height: 280 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
