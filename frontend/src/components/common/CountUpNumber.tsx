import { useEffect, useState } from 'react'

interface CountUpNumberProps {
  end: number
  duration?: number
  suffix?: string
  className?: string
}

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
