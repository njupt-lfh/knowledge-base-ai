/**
 * RAG 引用趋势折线图（ECharts）
 * 展示近 7 日对话引用命中趋势
 * 主要导出：默认 TrendLineChart 组件
 */
import type { EChartsOption } from 'echarts'
import type { TrendPoint } from '../../api/stats'
import ChartFillArea from './ChartFillArea'
import ResponsiveChart from './ResponsiveChart'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface TrendLineChartProps {
  points: TrendPoint[]
  /** 图表高度（px），驾驶舱一屏布局可传较小值 */
  chartHeight?: number
  /** 撑满父容器剩余高度（驾驶舱 Bento 网格） */
  fill?: boolean
}

/** 7 日 RAG 引用趋势线，带渐变面积填充 */
export default function TrendLineChart({
  points,
  chartHeight = 280,
  fill = false,
}: TrendLineChartProps) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: points.map((p) => p.date.slice(5)),
      axisLine: { lineStyle: { color: 'rgba(0,212,255,0.2)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(0,212,255,0.08)' } },
      axisLabel: { color: '#64748b', fontFamily: 'JetBrains Mono' },
    },
    series: [
      {
        type: 'line',
        data: points.map((p) => p.hits),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#00d4ff', width: 2 },
        itemStyle: { color: '#00d4ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0,212,255,0.3)' },
              { offset: 1, color: 'rgba(0,212,255,0)' },
            ],
          },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: 'rgba(0,212,255,0.3)',
      textStyle: { color: '#e2e8f0' },
    },
  }

  const chart = (h: number) => <ResponsiveChart option={option} height={h} />

  return (
    <HudPanel className={`chart-panel${fill ? ' chart-panel--fill' : ''}`}>
      <h3 className="chart-panel__title">RAG 引用趋势（7日 · 真实对话）</h3>
      {fill ? <ChartFillArea>{chart}</ChartFillArea> : chart(chartHeight)}
    </HudPanel>
  )
}
