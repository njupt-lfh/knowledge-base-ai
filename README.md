# AI 知识库管理平台 (KnowledgeBase AI)

基于 RAG 技术构建的 AI 知识库管理平台，支持知识生产、治理、检索、对话与运营分析的完整闭环。

## 技术栈

- **前端**: React 18 + TypeScript + Ant Design 6 + Vite
- **后端**: Python 3.11 + FastAPI + SQLAlchemy 2.0 + Chroma
- **AI**: 火山引擎豆包 API（对话、嵌入、图谱抽取）
- **数据库**: SQLite（异步 aiosqlite 驱动）

## 功能特性

### 知识生产与入库

- 拖拽上传 PDF / Markdown / TXT / 图片，自动解析、分块、向量化
- PDF 内嵌图片、多模态图片单独入库
- 手动录入文本知识；入库质量门禁与冲突检测
- 文件夹监听 / Webhook 增量同步（可选）
- AI 对话中提炼新知识，经缺口队列与门禁后入库

### 知识管理

- 知识库 CRUD、自定义分块参数
- 文档启用/禁用、批量操作、标签分类
- 知识块查看、编辑、状态切换
- 知识健康面板、冷知识治理、入库冲突处理
- 轻量知识图谱可视化

### 知识消费

- Hybrid 检索（向量 + BM25 FTS）+ RRF 融合
- Agentic-lite 专家对话（CRAG、SIM-RAG 多轮检索、SSE 流式输出、来源引用）
- 多轮对话历史、消息反馈
- 一键生成分享链接（无需登录访问）

### 运营与分析

- **数据驾驶舱**（`/stats`）：全局/单库概览、趋势、热力图、热度排行、引用 vs 命中、Sankey 等
- **评测看板**（`/eval`）：RAG 基线报告与阶段对比
- **补全任务**（`/gaps`）：知识缺口队列与人工补全

## 快速启动

### 1. 环境准备

- Node.js >= 20.19（推荐 22）
- Python >= 3.11

### 2. 配置环境变量

**后端**（项目根目录）：

```bash
cp .env.example .env
# 编辑 .env，至少配置：
#   VOLCENGINE_API_KEY=你的 API Key
#   VOLCENGINE_LLM_MODEL=对话接入点 ID（ep-xxx）
#   VOLCENGINE_EMBEDDING_MODEL=嵌入接入点 ID
#   GRAPH_EXTRACTION_MODEL=图谱抽取接入点 ID（可选）
# 无 API Key 时可设 LLM_MOCK_MODE=true（可浏览数据，对话为 Mock）
```

**前端**（`frontend/` 目录）：

```bash
cd frontend
cp .env.example .env
# 默认 VITE_API_BASE=http://localhost:8080，一般无需修改
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
# API 文档: http://localhost:8080/docs
```

> 请从 `backend/` 目录启动，以保证 `.env` 中相对路径（`./uploads`、`./chroma_data`）解析正确。

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
# 访问: http://localhost:5173
```

## 数据目录说明

运行时数据**默认不在 Git 中**（见 `.gitignore`）。克隆空仓库后需自行导入文档；若要保留已有知识库、对话、向量等，需一并拷贝下列目录/文件。

| 路径 | 内容 | 说明 |
|------|------|------|
| `data/knowledge_base.db` | SQLite 主库 | 知识库、文档元数据、对话、消息、标签、FTS 等 |
| `backend/chroma_data/` | Chroma 向量库 | 各知识库的 embedding 索引（`.env` 中 `CHROMA_PERSIST_DIR=./chroma_data` 且从 `backend/` 启动时） |
| `backend/uploads/` | 上传原始文件 | PDF、图片等（`.env` 中 `UPLOAD_DIR=./uploads`） |

打包提交前建议**先停止后端**，并对数据库执行 checkpoint，避免 WAL 文件损坏：

```bash
python -c "import sqlite3; c=sqlite3.connect('data/knowledge_base.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()"
```

**切勿**将含真实 `VOLCENGINE_API_KEY` 的 `.env` 提交到公开仓库；可只提交 `.env.example`。

## 项目结构

```
knowledge-base-ai/
├── frontend/                 # React 前端
│   ├── .env.example          # VITE_API_BASE 等
│   └── src/
│       ├── api/              # API 调用层
│       ├── components/       # 通用与业务组件
│       ├── pages/            # 页面（列表、详情、对话、驾驶舱、评测、缺口）
│       └── router/           # 路由
├── backend/                  # Python 后端
│   ├── uploads/              # 上传文件（运行时，gitignore）
│   ├── chroma_data/          # 向量持久化（运行时，gitignore）
│   └── app/
│       ├── api/              # 路由层
│       ├── models/           # SQLAlchemy 模型
│       ├── services/         # 业务逻辑（RAG、治理、图谱等）
│       └── core/             # 配置、数据库、Chroma
├── data/                     # SQLite 与评测报告（运行时，gitignore）
├── docs/
│   ├── ARCHITECTURE.md       # 架构说明
│   └── adr/                  # 架构决策记录（ADR）
└── .env.example              # 后端环境变量模板
```

## 架构与决策文档

- 系统架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 各阶段设计决策：[docs/adr/](docs/adr/)（Hybrid 检索、Agent、图谱、评测等）

## 代码质量

本地自检（与 CI 一致）：

```bash
# 前端
cd frontend && npm run check

# 后端
cd backend
pip install -r requirements-dev.txt
ruff check app tests scripts
ruff format --check app tests scripts
```

GitHub Actions（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）在 push/PR 时执行前端 check、后端 Ruff、pytest 与 DeepEval 门禁。
