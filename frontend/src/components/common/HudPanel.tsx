import type { ReactNode } from 'react'

interface HudPanelProps {
  children: ReactNode
  className?: string
  hot?: boolean
  style?: React.CSSProperties
}

export default function HudPanel({ children, className = '', hot = false, style }: HudPanelProps) {
  return (
    <div className={`hud-panel ${hot ? 'hud-panel--hot' : ''} ${className}`.trim()} style={style}>
      {children}
      <span className="hud-corner-br" />
    </div>
  )
}
