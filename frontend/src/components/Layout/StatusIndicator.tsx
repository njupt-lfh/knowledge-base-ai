import { useEffect, useState } from 'react'
import request from '../../api/request'
import './StatusIndicator.css'

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
