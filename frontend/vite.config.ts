/**
 * Vite 构建与开发服务器配置
 * - 开发端口 5174（5173 被占用时使用），与后端 CORS 一致
 * - host: true 允许局域网访问（便于手机/同网段调试）
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    host: true,
  },
})
