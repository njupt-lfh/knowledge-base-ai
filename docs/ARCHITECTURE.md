# AI 知识库管理平台 — 架构文档

## 1. 系统架构

```
┌────────────────────────────────────────────┐
│              前端 (React 18 + Ant Design)    │
│  KnowledgeList / KnowledgeDetail / ChatAgent │
│  Stats / ShareChat                           │
│  端口: 5173 (Vite dev)                       │
└──────────────────┬─────────────────────────┘
                   │ HTTP REST + SSE Stream
┌──────────────────▼─────────────────────────┐
│           后端 (Python 3.11 + FastAPI)       │
│  ┌──────────┐ ┌────────┐ ┌──────────────┐  │
│  │ API Layer│ │Services│ │   Storage     │  │
│  │ knowledge│ │ Chunk  │ │ SQLite (ORM)  │  │
│  │ document │ │ RAG    │ │ Chroma (向量)  │  │
│  │ chunk    │ │ Embed  │ │ 本地文件系统    │  │
│  │ chat     │ │   LLM  │ │               │  │
│  │ tag      │ │        │ │               │  │
│  └──────────┘ └────────┘ └──────────────┘  │
│              端口: 8080                      │
└──────────────────┬─────────────────────────┘
                   │ HTTPS
┌──────────────────▼─────────────────────────┐
│    火山引擎 Ark API                          │
│    Chat: Doubao-Seed-1.8 (流式)             │
│    Embedding: Doubao-embedding-vision (2048d)│
└────────────────────────────────────────────┘
```

## 2. 数据模型

```
KnowledgeBase (知识库)
  ├── name, description
  ├── chunk_size, chunk_overlap
  └── documents → Document[]

Document (来源文档)
  ├── filename, file_type (pdf/md/txt/manual)
  ├── status (processing/completed/error)
  ├── is_active
  └── chunks → Chunk[]

Chunk (知识条目)
  ├── content (文本内容)
  ├── chunk_index, char_count
  ├── is_active, hit_count
  └── (向量存储在 Chroma 中)

Tag (标签) ── DocumentTag ── Document

Conversation (对话) → Message[] (消息)
```

## 3. RAG Pipeline

```
用户提问
  → EmbeddingService.embed_query() [火山 API, 2048维]
  → Chroma query (余弦相似度, top_k×3 候选)
  → SQLite 过滤 is_active=false 的块
  → 相似度阈值过滤 (score > 0.3)
  → System Prompt 组装 (知识块 + 规则 + 历史)
  → LLM 流式生成 (Doubao-Seed-1.8, SSE)
  → 保存 Message + 更新 hit_count
```

## 4. 关键技术决策

| 决策 | 理由 |
|------|------|
| Chroma 嵌入式向量库 | 零配置，无需独立服务，适合 Demo |
| SQLite + aiosqlite | 异步驱动，零配置 |
| FastAPI BackgroundTasks | 替代 Celery，减少依赖 |
| 直接 httpx 调 API | 替代 LangChain，减少依赖层级 |
| Doubao-embedding-vision | 火山引擎唯一可用嵌入模型，多模态端点 |
| React StrictMode immutable | 避免 setState 双重调用导致数据污染 |

## 5. API 路由

| 前缀 | 模块 | 主要端点 |
|------|------|---------|
| `/api/knowledge-bases` | knowledge | CRUD, search, stats |
| `/api/knowledge-bases/{id}/documents` | document | upload, manual, batch, tags |
| `/api/documents/{id}/chunks` | chunk | list, update, status |
| `/api/conversations/...` | chat | create, messages, share, extract |
| `/api/knowledge-bases/{id}/tags` | tag | CRUD, document tags |
| `/api/share/{token}` | share | public access |

## 6. 部署

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080

# 前端
cd frontend
npm install
npm run dev
```
