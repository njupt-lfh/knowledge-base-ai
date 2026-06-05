# AI 知识库管理平台 (KnowledgeBase AI)

基于 RAG 技术构建的 AI 知识库管理平台，支持知识生产、治理、检索、对话与运营分析的完整闭环。

## 源码仓库

| 项 | 地址 |
|----|------|
| **GitHub** | https://github.com/njupt-lfh/knowledge-base-ai |
| **默认开发分支** | `dev` |
| **CI** | [`.github/workflows/ci.yml`](.github/workflows/ci.yml)（push / PR 触发） |

克隆：`git clone https://github.com/njupt-lfh/knowledge-base-ai.git`

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

- Hybrid 检索（向量 + BM25 FTS）+ RRF 融合 + Cross-Encoder 精排（可选）
- Agentic-lite 专家对话（CRAG、SIM-RAG、图谱 multi_hop、SSE 流式、来源引用）
- **快速模式**（AI 对话页开关，按知识库持久化）：请求体 `fast_mode=true` 时关闭 Cross-Encoder 精排、Post-hoc Guard、答案一致性，并将 `AGENT_MAX_ROUNDS` 设为 1；**保留** SIM-RAG、图谱 multi_hop 等以便演示 `agent_meta` 标签。SSE 会回传 `fast_mode`，消息条显示金色「快速模式」标签。实现见 `backend/app/core/chat_runtime.py`、`.env.example` 注释。
- 多轮对话历史、消息反馈、答案一致性校验（完整质量链路；快速模式时部分关闭）
- 一键生成分享链接（无需登录访问）

> **评测口径**：`/eval` 看板与 `run_rag_eval.py` 基线走**完整 RAG 链路**，不以对话页「快速模式」为准。需展示完整质量链路时请**关闭**快速模式；需要更快响应并保留 SIM-RAG / 图谱标签时可**开启**。

### 运营与分析

- **数据驾驶舱**（`/stats`）：全局/单库概览、趋势、热力图、热度排行、引用 vs 命中、Sankey 等
- **评测看板**（`/eval`）：RAG 基线报告、阶段对比、题型/知识库分维度
- **补全任务**（`/gaps`）：知识缺口队列与人工补全

## 阶段进展与质量改进路线

项目在 Phase 0–3 能力已落地的基础上，按 **「RAG 指标改善 + 评测体系改造」** 双主线推进：

| 文档 | 说明 |
|------|------|
| [**docs/RAG_IMPROVEMENT_ROADMAP.md**](docs/RAG_IMPROVEMENT_ROADMAP.md) | 根因分析、Week 0–5+ 实施路线、对外说明要点、里程碑表 |
| [**docs/EVAL.md**](docs/EVAL.md) | 数据集 v1/v2、双轨指标、脚本命令、Dashboard 说明 |
| [**docs/ARCHITECTURE.md**](docs/ARCHITECTURE.md) | 系统架构与 RAG 流水线 |
| [**docs/adr/**](docs/adr/) | 各阶段 ADR（Hybrid、Agent、图谱、评测等） |

**当前要点（2026-06）**：

- **Week 0** ✅：拒答 Prompt、Post-hoc Guard、Abstention 校准（v1 NRR=100%）
- **Week 1–2** ✅：Cross-Encoder、检索后过滤、评测 v2 与分维度报告；Phase 3 v1 回归 PASS
- **Week 3–4** 📋：结构分块 re-index + RAGAS 质量优化（目标 AR≥0.55）
- **Week 5+** 📋：CRAG 早停、HNSW、CI 自动化（对应 Phase 5 性能）

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
# 访问: http://localhost:5173  （vite.config.ts 默认端口）
```

## 评测与看板（常用命令）

在 `backend/` 目录执行，详见 [docs/EVAL.md](docs/EVAL.md)。

```bash
# v1 全量检索基线（更新 Dashboard 召回/命中，约 30–40 分钟）
python scripts/run_rag_eval.py --dataset v1 --retrieval-only --limit 0

# v1 全量含 RAGAS（忠实度/答案相关性，数小时）
python scripts/run_rag_eval.py --dataset v1 --limit 0 --ragas

# Phase 3 出口门禁
python scripts/run_phase3_exit.py --report-only

# multi_hop 检索诊断
python scripts/diagnose_multi_hop_retrieval.py --limit 0
```

看板展示：启动前后端后打开 **`/eval`**，数据来自 `data/eval_baseline_report.json`（需先跑评测脚本生成）。

## 数据目录说明

运行时数据**默认不在 Git 中**（见 `.gitignore`）。克隆空仓库后需自行导入文档；若要保留已有知识库、对话、向量等，需一并拷贝下列目录/文件。

| 路径 | 内容 | 说明 |
|------|------|------|
| `data/knowledge_base.db` | SQLite 主库 | 知识库、文档元数据、对话、消息、标签、FTS、评测历史等 |
| `backend/chroma_data/` | Chroma 向量库 | 各知识库的 embedding 索引 |
| `backend/uploads/` | 上传原始文件 | PDF、图片等 |
| `data/eval_baseline_report.json` | 评测基线 | 前端 `/eval` 读取 |
| `data/eval_qa_dataset.json` | 评测集 v1 | 100 条回归集 |
| `data/eval_qa_dataset_v2.json` | 评测集 v2 | 扩展集 |

打包提交前建议**先停止后端**，并对数据库执行 checkpoint：

```bash
python -c "import sqlite3; c=sqlite3.connect('data/knowledge_base.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()"
```

**切勿**将含真实 `VOLCENGINE_API_KEY` 的 `.env` 提交到公开仓库。

## 项目结构

```
knowledge-base-ai/
├── frontend/                 # React 前端（dev 端口 5173）
│   ├── .env.example
│   └── src/
│       ├── api/              # API 调用层
│       ├── components/       # 通用与业务组件
│       ├── pages/            # 列表、详情、对话、驾驶舱、评测、缺口
│       ├── data/             # evalPhaseComparison 等静态快照
│       └── router/
├── backend/
│   ├── uploads/              # 上传文件（运行时）
│   ├── chroma_data/          # 向量持久化（运行时）
│   ├── scripts/              # 评测、Phase 出口、数据集构建
│   └── app/
│       ├── api/
│       ├── eval/             # 聚合、CI 门禁、RAGAS
│       ├── models/
│       ├── services/         # RAG、治理、图谱、Cross-Encoder 等
│       └── core/
├── data/                     # SQLite、评测报告（运行时）
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RAG_IMPROVEMENT_ROADMAP.md   # RAG 指标改善路线图
│   ├── EVAL.md                     # 评测体系说明
│   └── adr/
└── .env.example
```

## 架构与决策文档

- 系统架构：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- RAG 指标改善路线图：[docs/RAG_IMPROVEMENT_ROADMAP.md](docs/RAG_IMPROVEMENT_ROADMAP.md)
- 评测体系：[docs/EVAL.md](docs/EVAL.md)
- 阶段 ADR：[docs/adr/](docs/adr/)

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
pytest tests/ -q --override-ini="addopts="
```

GitHub Actions（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）在 push/PR 时执行前端 check、后端 Ruff、pytest 与 DeepEval 门禁。
