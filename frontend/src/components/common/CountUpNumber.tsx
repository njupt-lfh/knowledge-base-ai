/**
 * 数字递增动画组件
 * 用于统计卡片等场景的 CountUp 效果
 * 主要导出：默认 CountUpNumber 组件
 */
import { useEffect, useState } from 'react'

interface CountUpNumberProps {
  end: number
  duration?: number
  suffix?: string
  className?: string
}

/**
 * 从 0 动画递增到目标值
 * @param end 目标数值
 * @param duration 动画时长（秒）
 * @param suffix 数字后后缀
 */
export default function CountUpNumber({
  end,
  duration = 1.2,
  suffix = '',
  className = 'hud-stat-value',
}: CountUpNumberProps) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    let frame = 0
    const start = performance.now()
    const from = 0

    const tick = (now: number) => {
      const progress = Math.min((now - start) / (duration * 1000), 1)
      setValue(Math.round(from + (end - from) * progress))
      if (progress < 1) {
        frame = requestAnimationFrame(tick)
      }
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [end, duration])

  return (
    <span className={className}>
      {value.toLocaleString()}
      {suffix}
    </span>
  )
}
