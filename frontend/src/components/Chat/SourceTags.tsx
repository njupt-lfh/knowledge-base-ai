/**
 * RAG 引用来源折叠列表
 * 展示检索到的 chunk 摘要与相似度分数
 * 主要导出：默认 SourceTags 组件
 */
import { useState } from 'react'
import { DownOutlined, UpOutlined, LinkOutlined } from '@ant-design/icons'
import type { SourceItem } from '../../types'
import './SourceTags.css'

interface SourceTagsProps {
  sources: SourceItem[]
}

/** 可展开/收起的知识链路引用区 */
export default function SourceTags({ sources }: SourceTagsProps) {
  const [expanded, setExpanded] = useState(false)

  if (!sources.length) return null

  return (
    <div className="source-tags">
      <button type="button" className="source-tags__toggle" onClick={() => setExpanded(!expanded)}>
        <LinkOutlined />
        知识链路 {sources.length} 条{expanded ? <UpOutlined /> : <DownOutlined />}
      </button>
      {expanded && (
        <div className="source-tags__list">
          {sources.map((s, i) => (
            <div key={i} className="source-tags__item">
              <span className="source-tags__score">[{s.score.toFixed(2)}]</span>
              {s.content.slice(0, 120)}
              {s.content.length > 120 ? '...' : ''}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
