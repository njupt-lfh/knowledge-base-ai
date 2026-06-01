/**
 * 根应用组件
 * 负责：注入 React Router 路由提供者
 * 主要导出：默认 App 组件
 */
import { RouterProvider } from 'react-router-dom'
import router from './router'

/** 应用根组件，挂载全局路由 */
export default function App() {
  return <RouterProvider router={router} />
}
