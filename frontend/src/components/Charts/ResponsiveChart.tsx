/**

 * ECharts 响应式容器：容器尺寸变化时自动 resize，避免图表拉伸变形。

 */

import { useCallback, useEffect, useRef } from 'react'

import ReactECharts from 'echarts-for-react'

import type { EChartsOption } from 'echarts'

interface ResponsiveChartProps {
  option: EChartsOption

  height: number

  notMerge?: boolean

  lazyUpdate?: boolean
}

export default function ResponsiveChart({
  option,

  height,

  notMerge,

  lazyUpdate,
}: ResponsiveChartProps) {
  const chartRef = useRef<ReactECharts>(null)

  const wrapRef = useRef<HTMLDivElement>(null)

  const resize = useCallback(() => {
    chartRef.current?.getEchartsInstance()?.resize()
  }, [])

  useEffect(() => {
    resize()

    requestAnimationFrame(() => {
      resize()

      requestAnimationFrame(resize)
    })
  }, [height, resize])

  useEffect(() => {
    const el = wrapRef.current

    if (!el) return

    resize()

    const ro = new ResizeObserver(resize)

    ro.observe(el)

    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) resize()
      },

      { threshold: 0 },
    )

    io.observe(el)

    return () => {
      ro.disconnect()

      io.disconnect()
    }
  }, [resize])

  return (
    <div ref={wrapRef} className="responsive-chart" style={{ height, width: '100%' }}>
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'canvas' }}
        notMerge={notMerge}
        lazyUpdate={lazyUpdate}
      />
    </div>
  )
}
