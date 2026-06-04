/**
 * Agent 检索元信息条
 * 展示路由类型、检索轮次、SIM-RAG、图谱、拒答等 SSE agent_meta 字段
 * 主要导出：AgentMeta 类型、默认 AgentMetaStrip 组件
 */
import { Tag, Typography } from 'antd'

/** 流式事件中 agent_meta 载荷 */
export interface AgentMeta {
  route?: string
  rounds?: number
  sim_rag_used?: boolean
  sim_sub_queries?: string[]
  sim_coverage?: number
  crag_score?: number
  graph_used?: boolean
  refused?: boolean
  fast_mode?: boolean
}

const ROUTE_LABEL: Record<string, string> = {
  factual: '事实',
  relational: '关系',
  comprehensive: '综合',
  chitchat: '闲聊',
}

/**
 * 助手消息下方的 Agent 决策标签条
 * @param meta agent_meta 事件解析结果
 */
export default function AgentMetaStrip({ meta }: { meta: AgentMeta }) {
  if (!meta) return null

  return (
    <div className="agent-meta-strip">
      {meta.route && <Tag color="blue">路由 {ROUTE_LABEL[meta.route] || meta.route}</Tag>}
      {typeof meta.rounds === 'number' && <Tag>检索 {meta.rounds} 轮</Tag>}
      {meta.graph_used && <Tag color="purple">图谱</Tag>}
      {meta.sim_rag_used && (
        <Tag color="cyan">SIM-RAG · 覆盖 {(meta.sim_coverage ?? 0) * 100}%</Tag>
      )}
      {meta.sim_rag_used && meta.sim_sub_queries && meta.sim_sub_queries.length > 0 && (
        <Typography.Text type="secondary" className="agent-meta-strip__subs">
          子问题：{meta.sim_sub_queries.join(' · ')}
        </Typography.Text>
      )}
      {meta.fast_mode && <Tag color="gold">快速模式</Tag>}
      {meta.refused && <Tag color="orange">已拒答</Tag>}
    </div>
  )
}
