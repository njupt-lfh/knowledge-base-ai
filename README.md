# AI 知识库管理平台 (KnowledgeBase AI)

基于 RAG 技术构建的 AI 知识库管理平台，支持知识生产、管理和消费的完整闭环。

## 技术栈

- **前端**: React 18 + TypeScript + Ant Design 5 + Vite
- **后端**: Python 3.11 + FastAPI + SQLAlchemy 2.0 + Chroma
- **AI**: 火山引擎豆包 API (Doubao-Seed-1.8 Chat + Doubao-embedding-vision)
- **数据库**: SQLite (异步 aiosqlite 驱动)

## 功能特性

### 知识生产
- 拖拽上传 PDF / Markdown / TXT 文件，自动解析分块向量化
- 手动录入文本知识
- AI 对话中自动提炼新知识（加分项）

### 知识管理
- 知识库 CRUD + 自定义分块参数
- 文档启用/禁用、批量操作
- 知识块查看、编辑、状态切换
- 标签分类管理

### 知识消费
- RAG 专家对话（SSE 流式输出 + 来源引用）
- 多轮对话历史
- 一键生成分享链接（无需登录访问）

### 统计分析
- 知识热度排行（命中次数统计）
- 全局/知识库级数据概览

## 快速启动

### 1. 环境准备
- Node.js >= 20.19（ESLint 10 要求；推荐 22）
- Python >= 3.11

### 2. 配置
```bash
cp .env.example .env
# 编辑 .env:
#   VOLCENGINE_API_KEY=你的API Key
#   VOLCENGINE_LLM_MODEL=你的对话接入点ID
#   VOLCENGINE_EMBEDDING_MODEL=你的嵌入接入点ID
#   LLM_MOCK_MODE=false
```

### 3. 启动后端
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
# API 文档: http://localhost:8080/docs
```

### 4. 启动前端
```bash
cd frontend
npm install
npm run dev
# 访问: http://localhost:5173
```

## 项目结构

```
knowledge-base-ai/
├── frontend/              # React 前端
│   └── src/
│       ├── api/           # API 调用层
│       ├── components/    # 通用组件
│       ├── pages/         # 页面组件
│       ├── router/        # 路由配置
│       └── types/         # TypeScript 类型
├── backend/               # Python 后端
│   └── app/
│       ├── api/           # 路由层
│       ├── models/        # SQLAlchemy 模型
│       ├── schemas/       # Pydantic 模型
│       ├── services/      # 业务逻辑
│       └── core/          # 配置/数据库/Chroma
├── docs/                  # 文档
└── data/                  # 数据存储
```

## 架构说明

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 代码质量

本地自检（与 CI 一致）：

```bash
# 前端：TypeScript + ESLint + Prettier
cd frontend
npm run check

# 后端：Ruff lint + format
cd backend
pip install -r requirements-dev.txt
ruff check app tests scripts
ruff format --check app tests scripts
```

GitHub Actions（`.github/workflows/ci.yml`）在 push/PR 时并行执行：

| Job | 内容 |
|-----|------|
| `frontend-quality` | `npm run check` |
| `backend-lint` | `ruff check` + `ruff format --check` |
| `backend` | pytest + DeepEval 门禁（已有） |

详细方案见 `开发文档/代码质量工具集成方案-合并版.md`。

## 开发文档

完整开发方案见 [AI知识库管理平台-开发方案文档.md](../AI知识库管理平台-开发方案文档.md)
