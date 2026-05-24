import { motion } from 'framer-motion'
import { PlusOutlined } from '@ant-design/icons'

interface CreateCardProps {
  onClick: () => void
  index?: number
}

export default function CreateCard({ onClick, index = 0 }: CreateCardProps) {
  return (
    <motion.button
      type="button"
      className="create-card"
      onClick={onClick}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <PlusOutlined className="create-card__icon" />
      <span className="create-card__label">新建知识库</span>
    </motion.button>
  )
}
