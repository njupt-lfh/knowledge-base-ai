import { Tag, Typography } from 'antd'

export interface AgentMeta {
  route?: string
  rounds?: number
  sim_rag_used?: boolean
  sim_sub_queries?: string[]
  sim_coverage?: number
  crag_score?: number
  graph_used?: boolean
  refused?: boolean
}

const ROUTE_LABEL: Record<string, string> = {
  factual: '事实',
  relational: '关系',
  comprehensive: '综合',
  chitchat: '闲聊',
}

export default function AgentMetaStrip({ meta }: { meta: AgentMeta }) {
  if (!meta) return null

  return (
    <div className="agent-meta-strip">
      {meta.route && (
        <Tag color="blue">路由 {ROUTE_LABEL[meta.route] || meta.route}</Tag>
      )}
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
      {meta.refused && <Tag color="orange">已拒答</Tag>}
    </div>
  )
}
