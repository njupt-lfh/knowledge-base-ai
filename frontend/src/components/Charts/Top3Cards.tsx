/**
 * 全局 TOP3 热知识卡片
 * 展示命中次数最高的三条 chunk 摘要
 * 主要导出：默认 Top3Cards 组件
 */
import { motion } from 'framer-motion'
import { FireOutlined } from '@ant-design/icons'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface Top3CardsProps {
  items: { content: string; hits: number }[]
}

/** 驾驶舱全局最热三条知识文本卡片 */
export default function Top3Cards({ items }: Top3CardsProps) {
  const top3 = items.slice(0, 3)

  return (
    <HudPanel hot className="chart-panel">
      <h3 className="chart-panel__title">
        <FireOutlined style={{ color: 'var(--accent-hot)', marginRight: 8 }} />
        全局 TOP 3 热知识
      </h3>
      <div className="top3-grid">
        {top3.length === 0 && (
          <p style={{ color: 'var(--text-muted)', fontSize: 13, gridColumn: '1 / -1' }}>
            暂无命中数据，请先使用检索或对话功能
          </p>
        )}
        {top3.map((item, i) => (
          <motion.div
            key={i}
            className="top3-card"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1 }}
          >
            <div className="top3-card__rank">#{i + 1}</div>
            <div className="top3-card__content">{item.content}</div>
            <div className="top3-card__hits">{item.hits} 次命中</div>
          </motion.div>
        ))}
      </div>
    </HudPanel>
  )
}
