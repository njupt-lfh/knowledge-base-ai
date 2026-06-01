/**
 * HUD 风格面板容器
 * 带右下角装饰角的通用内容区包装
 * 主要导出：默认 HudPanel 组件
 */
import type { ReactNode } from 'react'

interface HudPanelProps {
  children: ReactNode
  className?: string
  hot?: boolean
  style?: React.CSSProperties
}

/**
 * HUD 面板：可选 hot 高亮样式
 * @param hot 是否使用「热点」边框强调
 */
export default function HudPanel({ children, className = '', hot = false, style }: HudPanelProps) {
  return (
    <div className={`hud-panel ${hot ? 'hud-panel--hot' : ''} ${className}`.trim()} style={style}>
      {children}
      <span className="hud-corner-br" />
    </div>
  )
}
