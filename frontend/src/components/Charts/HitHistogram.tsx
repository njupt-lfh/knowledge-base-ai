/**
 * 热度分布直方图（ECharts）
 * 按命中次数区间统计 chunk 数量
 * 主要导出：默认 HitHistogram 组件
 */
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { HitBucket } from '../../api/stats'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface HitHistogramProps {
  buckets: HitBucket[]
}

/** 单库 chunk 命中次数分桶柱状图 */
export default function HitHistogram({ buckets }: HitHistogramProps) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: buckets.map((b) => b.label),
      axisLabel: { color: '#94a3b8', fontFamily: 'JetBrains Mono', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.2)' } },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.08)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono' },
    },
    series: [
      {
        type: 'bar',
        data: buckets.map((b) => b.count),
        barWidth: 36,
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: (params) => {
            const colors = ['#64748b', '#00d4ff', '#33ddff', '#ff6b35']
            return colors[params.dataIndex as number] ?? '#00d4ff'
          },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.name}<br/><b>${p.value} 个知识块</b>`
      },
    },
  }

  return (
    <HudPanel className="chart-panel">
      <h3 className="chart-panel__title">热度分布直方图</h3>
      <ReactECharts option={option} style={{ height: 260 }} opts={{ renderer: 'canvas' }} />
    </HudPanel>
  )
}
