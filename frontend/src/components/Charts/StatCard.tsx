import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import CountUpNumber from '../common/CountUpNumber'
import HudPanel from '../common/HudPanel'
import './StatCard.css'

interface StatCardProps {
  title: string
  value: number
  icon: ReactNode
  delta?: string
  hot?: boolean
  index?: number
}

export default function StatCard({
  title,
  value,
  icon,
  delta,
  hot = false,
  index = 0,
}: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.35 }}
    >
      <HudPanel hot={hot} className="stat-card">
        <div className="stat-card__header">
          <span className="stat-card__icon">{icon}</span>
          <span className="hud-stat-label">{title}</span>
        </div>
        <CountUpNumber end={value} />
        {delta && <span className="stat-card__delta">{delta}</span>}
      </HudPanel>
    </motion.div>
  )
}
