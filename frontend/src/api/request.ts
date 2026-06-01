/**
 * Axios HTTP 客户端封装
 * 统一 baseURL、超时与错误日志
 * 主要导出：默认 request 实例
 */
import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8080',
  timeout: 60000,
})

// 响应拦截：记录 API 错误后原样 reject，由调用方处理
request.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  },
)

export default request
