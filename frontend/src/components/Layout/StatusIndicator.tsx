/**
 * 后端健康状态指示器
 * 定时轮询 /api/health 显示在线/离线
 * 主要导出：默认 StatusIndicator 组件
 */
import { useEffect, useState } from 'react'
import request from '../../api/request'
import './StatusIndicator.css'

/** 每 30 秒检测一次后端连通性 */
export default function StatusIndicator() {
  const [online, setOnline] = useState<boolean | null>(null)

  useEffect(() => {
    const check = () => {
      request
        .get('/api/health')
        .then(() => setOnline(true))
        .catch(() => setOnline(false))
    }
    check()
    const timer = setInterval(check, 30000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="status-indicator">
      <span
        className={`status-indicator__dot ${online === true ? 'status-indicator__dot--online' : online === false ? 'status-indicator__dot--offline' : ''}`}
      />
      <span className="status-indicator__text">
        {online === null ? '检测中...' : online ? '系统在线' : '连接断开'}
      </span>
    </div>
  )
}
