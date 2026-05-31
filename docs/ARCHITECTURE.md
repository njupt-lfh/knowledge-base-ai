# AI 知识库管理平台 — 架构文档

## 1. 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                    前端 (React 18 + Ant Design)               │
│  KnowledgeList / KnowledgeDetail / ChatAgent / GapTasks      │
│  Stats（数据驾驶舱）/ EvalDashboard / ShareChat               │
│  端口: 5173 (Vite dev)  →  API: http://localhost:8080        │
└────────────────────────────┬─────────────────────────────────┘
                             │ HTTP REST + SSE Stream
┌────────────────────────────▼─────────────────────────────────┐
│                 后端 (Python 3.11 + FastAPI)                  │
│  ┌──────────┐ ┌─────────────┐ ┌──────────────────────────┐   │
│  │ API Layer│ │  Services   │ │        Storage            │   │
│  │ knowledge│ │ Hybrid RAG  │ │ SQLite (ORM + FTS5)       │   │
│  │ document │ │ CRAG/Agent  │ │ Chroma (向量, 按 KB 分库)  │   │
│  │ chat     │ │ Governance  │ │ backend/uploads (文件)    │   │
│  │ stats    │ │ Graph/Gap   │ │                           │   │
│  └──────────┘ └─────────────┘ └──────────────────────────┘   │
│                    端口: 8080                                 │
└────────────────────────────┬─────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼─────────────────────────────────┐
│              火山引擎 Ark API                                   │
│  Chat / Embedding / 图谱三元组抽取                             │
└──────────────────────────────────────────────────────────────┘
```

### 前端路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/knowledge-bases` | 知识库列表 | CRUD、检索入口 |
| `/knowledge-bases/:kbId` | 知识库详情 | 文档、检索测试、图谱、同步、治理、冲突 |
| `/knowledge-bases/:kbId/chat` | AI 专家对话 | SSE 流式 RAG 对话 |
| `/knowledge-bases/:kbId/gaps` | 补全任务 | 知识缺口队列 |
| `/stats` | 数据驾驶舱 | 全局/单库运营指标 |
| `/eval` | 评测看板 | RAG 基线与阶段对比 |
| `/share/:token` | 分享对话 | 免登录只读 |

## 2. 数据模型（核心）

```
KnowledgeBase
  ├── documents → Document
  │     └── chunks → Chunk（向量在 Chroma，全文在 chunks_fts）
  ├── tags → Tag（经 DocumentTag 关联文档）
  ├── conversations → Conversation → Message
  ├── gaps（知识缺口队列）
  └── graph 实体/关系（轻量图谱）

Chunk: content, is_active, hit_count, quality 等
```

持久化路径（从 `backend/` 启动、使用根目录 `.env.example` 默认值时）：

| 存储 | 路径 |
|------|------|
| 关系库 | `../data/knowledge_base.db` |
| 向量库 | `backend/chroma_data/` |
| 上传文件 | `backend/uploads/` |

## 3. RAG Pipeline（当前）

```
用户提问
  → HybridRetriever
       ├─ Chroma 向量检索（top 候选）
       └─ SQLite FTS5 BM25 检索
       → RRF 融合排序
  → CRAG-lite 质量门（分数 / 词重叠阈值，低质可拒答或改写查询）
  → Agentic-lite（可选多轮 SIM-RAG 子查询扩展）
  → 轻量知识图谱增强（可选）
  → System Prompt 组装（知识块 + 规则 + 截断历史）
  → LLM 流式生成（SSE）
  → 保存 Message、更新 hit_count、返回 sources
```

Mock 模式（`LLM_MOCK_MODE=true`）：跳过真实 LLM/嵌入调用，便于无 Key 环境下冒烟与 UI 验证。

## 4. 关键技术决策

| 决策 | 理由 |
|------|------|
| Chroma 嵌入式向量库 | 零配置，适合本地 Demo 与交付打包 |
| SQLite + FTS5 + aiosqlite | 结构化数据与 BM25 同库，异步驱动 |
| Hybrid + RRF | 弥补纯向量语义漂移，提升专有名词召回 |
| FastAPI BackgroundTasks | 文档解析异步化，不引入 Celery |
| 直接 httpx 调 Ark API | 减少 LangChain 等中间层 |
| ADR 文档化阶段演进 | 见 `docs/adr/`，便于答辩与维护 |

## 5. API 路由概览

| 前缀 / 模块 | 主要能力 |
|-------------|----------|
| `/api/knowledge-bases` | 知识库 CRUD、Hybrid 检索 |
| `/api/knowledge-bases/{id}/documents` | 上传、手动录入、批量状态 |
| `/api/documents/{id}/chunks` | 知识块列表、编辑、启停 |
| `/api/knowledge-bases/{id}/tags` | 标签 CRUD、文档打标 |
| `/api/knowledge-bases/{id}/conversations` | 对话列表 |
| `/api/conversations/{id}/chat` | SSE 流式对话 |
| `/api/conversations/{id}/extract-knowledge` | 对话提炼入库 |
| `/api/share/{token}` | 分享只读 |
| `/api/knowledge-bases/{id}/governance` | 冷知识治理建议 |
| `/api/knowledge-bases/{id}/conflicts` | 入库冲突 |
| `/api/knowledge-bases/{id}/gaps` | 缺口队列与 ingest |
| `/api/knowledge-bases/{id}/.../graph` | 知识图谱 |
| `/api/sync` | 文件夹监听 / Webhook 同步 |
| `/api/stats/*` | 驾驶舱：概览、趋势、热力图、分布、Sankey 等 |
| `/api/eval/*` | 评测基线报告 |
| `/api/knowledge-bases/{id}/feedback` | 消息反馈 |

完整端点见 Swagger：`http://localhost:8080/docs`

## 6. 本地部署

**环境变量**

- 根目录 `.env`：火山 API、数据库、Chroma、上传目录、Mock 开关等（见 `.env.example`）
- `frontend/.env`：`VITE_API_BASE=http://localhost:8080`

**启动**

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080

# 前端
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

**CORS**：后端允许 `localhost:5173`（及 5174 备用）来源。

**交付含数据时**：连同 `data/knowledge_base.db`、`backend/chroma_data/`、`backend/uploads/` 打包；不要泄露 `.env` 中的 API Key。

## 7. 相关文档

- 阶段决策记录：[docs/adr/](adr/)
- 使用说明与数据目录：[../README.md](../README.md)
