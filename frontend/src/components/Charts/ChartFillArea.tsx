/**

 * 图表自适应高度区域：撑满 chart-panel 标题以下空间，供 ECharts 使用。

 */

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useChartRemeasureKey } from './ChartLayoutContext'

interface ChartFillAreaProps {
  children: (height: number) => ReactNode

  minHeight?: number

  /** Tab 切换等场景触发重新测量 */

  remeasureKey?: string | number
}

function measureHeight(el: HTMLElement, minHeight: number) {
  return Math.max(minHeight, Math.floor(el.clientHeight))
}

export default function ChartFillArea({
  children,
  minHeight = 72,
  remeasureKey: remeasureKeyProp,
}: ChartFillAreaProps) {
  const remeasureKeyCtx = useChartRemeasureKey()
  const remeasureKey = remeasureKeyProp ?? remeasureKeyCtx
  const ref = useRef<HTMLDivElement>(null)
  const [height, setHeight] = useState<number | null>(null)

  useEffect(() => {
    const el = ref.current

    if (!el) return

    const update = () => {
      const next = measureHeight(el, minHeight)

      if (next > 0) setHeight(next)
    }

    const scheduleUpdate = () => {
      update()

      requestAnimationFrame(() => {
        update()

        requestAnimationFrame(update)
      })
    }

    scheduleUpdate()

    const timers = [0, 50, 150, 300].map((ms) => window.setTimeout(scheduleUpdate, ms))

    const ro = new ResizeObserver(scheduleUpdate)

    ro.observe(el)

    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) scheduleUpdate()
      },

      { threshold: 0 },
    )

    io.observe(el)

    window.addEventListener('resize', scheduleUpdate)

    return () => {
      timers.forEach((id) => window.clearTimeout(id))

      ro.disconnect()

      io.disconnect()

      window.removeEventListener('resize', scheduleUpdate)
    }
  }, [minHeight, remeasureKey])

  return (
    <div ref={ref} className="chart-fill-area">
      {height !== null && height > 0 ? children(height) : null}
    </div>
  )
}
