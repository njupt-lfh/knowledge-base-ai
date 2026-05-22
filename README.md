# AI 知识库管理平台 (KnowledgeBase AI)

基于 RAG 技术构建的 AI 知识库管理平台，支持知识生产、管理和消费的完整闭环。

## 技术栈

- **前端**: React 18 + TypeScript + Ant Design 5 + Vite
- **后端**: Python FastAPI + SQLAlchemy 2.0 + Chroma
- **AI**: 火山引擎豆包 API (Chat + Embedding)
- **数据库**: SQLite (开发) / PostgreSQL (生产可选)

## 快速启动

### 1. 环境准备

- Node.js >= 18
- Python >= 3.11

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 VOLCENGINE_API_KEY
```

### 3. 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API 文档: http://localhost:8000/docs

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问: http://localhost:5173

## 项目结构

```
knowledge-base-ai/
├── frontend/          # React 前端
├── backend/           # Python 后端
├── docs/              # 文档
├── scripts/           # 脚本
├── uploads/           # 上传文件
├── data/              # 数据库文件
└── chroma_data/       # 向量存储
```

## 架构说明

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 团队分工

| 角色 | 职责 |
|------|------|
| 后端核心 | 数据库设计、知识库/文档 CRUD API、Chroma 集成 |
| AI 与对话 | 火山引擎 API、RAG 管道、SSE 流式 |
| 前端开发 | 管理界面、文档上传、对话页面 |

## 开发文档

完整开发方案见 [AI知识库管理平台-开发方案文档.md](../AI知识库管理平台-开发方案文档.md)
