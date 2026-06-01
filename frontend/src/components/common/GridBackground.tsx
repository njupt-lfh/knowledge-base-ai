/**
 * 全屏网格背景装饰
 * 用于分享页等独立布局的科技感底纹
 * 主要导出：默认 GridBackground 组件
 */
import './GridBackground.css'

/** 纯装饰性背景层，对屏幕阅读器隐藏 */
export default function GridBackground() {
  return (
    <div className="grid-background" aria-hidden="true">
      <div className="grid-background__layer" />
      <div className="grid-background__vignette" />
    </div>
  )
}
