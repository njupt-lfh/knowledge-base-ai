# Knowledge Base AI — 前端

React 18 + TypeScript + Ant Design 6 + Vite + ECharts + framer-motion。

## 开发

```bash
cp .env.example .env   # VITE_API_BASE=http://localhost:8080
npm install
npm run dev            # http://localhost:5173
```

需先启动后端（见项目根目录 [README.md](../README.md)）。

## 常用命令

| 命令             | 说明                                      |
| ---------------- | ----------------------------------------- |
| `npm run dev`    | 开发服务器（端口 5173）                   |
| `npm run build`  | 生产构建（含 `tsc -b` 类型检查）          |
| `npm run check`  | TypeScript + ESLint + Prettier（CI 一致） |
| `npm run lint`   | ESLint 检查                               |
| `npm run format` | Prettier 格式化                           |

## 主要页面

- `KnowledgeList` / `KnowledgeDetail` — 知识库与文档管理
- `ChatAgent` — AI 专家对话
- `Stats` — 数据驾驶舱
- `EvalDashboard` — 评测看板
- `GapTasks` — 补全任务

路由定义见 `src/router/index.tsx`。
