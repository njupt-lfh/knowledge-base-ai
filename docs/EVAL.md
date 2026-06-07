# 评测体系说明

> **版本**：v1.1  
> **更新**：2026-06-04  
> **关联**：[RAG 改善路线图](RAG_IMPROVEMENT_ROADMAP.md) · [ADR-000](adr/ADR-000-评测体系.md)

本文描述仓库内 **可执行的评测口径、数据集、脚本与评测看板展示**。

---

## 1. 设计原则

1. **v1 保留作回归基线**，不可破坏性改名 `data/eval_qa_dataset.json`。
2. **v2 并行建设**（更难、更贴近真实），用于 multi_hop / 负例近域干扰等。
3. **双轨指标**：chunk 级（IR）与 RAGAS（生成）分开命名、分开展示。
4. **分维度报告**：`by_question_type`、`by_kb`（`EvalDashboard` 已支持）。
5. **历史趋势**：全量跑评写入 `eval_runs` 表（`GET /api/eval/runs`）。

---

## 2. 数据集

| 文件 | 版本 | 样本量 | 用途 |
|------|------|--------|------|
| `data/eval_qa_dataset.json` | v1 | 100（5 库×20） | 回归基线、Phase 3 v1 门禁、看板主展示 |
| `data/eval_qa_dataset_v2.json` | v2 | 168+ | 多 relevant、近域负例、自然问法 |

**题型占比（v1）**：fact 50% · concept 20% · multi_hop 20% · negative 10%。

**v2 增强**（详见 `scripts/build_eval_dataset.py`）：

- `relevant_chunk_ids` 多条 + 可选 `relevance_grades`（NDCG）
- `negative_subtype`：`irrelevant` / `near_domain`
- 优先从 `kg_relations` 生成 multi_hop 问法

---

## 3. 指标定义（禁止混称）

| 前端 / 报告字段 | 简称 | 含义 |
|-----------------|------|------|
| `context_precision_chunk` | **CP-chunk** | \|相关∩检索\| / \|检索\| |
| `context_recall_chunk` | **CR-chunk** | \|相关∩检索\| / \|相关\| |
| `context_precision_mean` | 同 CP-chunk 聚合 | 与 chunk 字段一致 |
| `ragas.context_precision` | **CP-ragas** | RAGAS LLM 判别 |
| `ragas.context_recall` | **CR-ragas** | RAGAS LLM 判别 |
| `faithfulness_mean` | **FA** | 回答是否 grounded |
| `answer_relevancy_mean` | **AR** | 回答是否对准问题 |
| `negative_reject_rate` | **NRR** | 负例空检索比例 |
| `retrieval_hit_rate` | 命中率 | 正例是否命中至少一个 relevant |
| `mrr_mean` / `ndcg_at_5_mean` | MRR / NDCG@5 | 排序质量（正例） |

---

## 4. 脚本与命令

均在 **`backend/`** 目录执行。

### 4.1 全量基线（看板 Dashboard 数据源）

```bash
# 仅检索（快，约 30–40 分钟 / 100 条）
python scripts/run_rag_eval.py --dataset v1 --retrieval-only --limit 0

# 检索 + 生成 + RAGAS（慢，数小时）
python scripts/run_rag_eval.py --dataset v1 --limit 0 --ragas
```

产出：

- `data/eval_baseline_report.json` ← 前端 `GET /api/eval/baseline` **只读此文件**
- `data/eval_baseline_report_v1.json` / `_v2.json` 分版本存档

### 4.2 Phase 3 出口

```bash
python scripts/run_phase3_exit.py --report-only
```

门禁（`data/phase3_exit_report.json`）：

| 门禁 | 条件 |
|------|------|
| v1 回归 | CR-chunk ≥ 0.85，NRR = 1.0（读 `eval_baseline_report_v1.json`） |
| v2 multi_hop | CR ≥ 0.82，样本 ≥ 50（读 `eval_baseline_report_v2.json`） |

### 4.3 多跳检索诊断

```bash
python scripts/diagnose_multi_hop_retrieval.py --limit 0
```

### 4.4 CI 门禁

```bash
python scripts/run_rag_eval.py --dataset v1 --retrieval-only --limit 30 --ci-mode --ci-phase week0
python scripts/check_eval_ci_gates.py --report ../data/eval_baseline_report.json --phase week2
```

阈值定义：`backend/app/eval/ci_gates.py`。

---

## 5. 前端展示

| 路由 | 说明 |
|------|------|
| `/eval` | 评测看板：当前报告 KPI + RAGAS 子块 + 题型/知识库 Tab |
| 静态对比 | `frontend/src/data/evalPhaseComparison.ts`（Phase 0–3 历史快照，需手动更新） |

**开发端口**：Vite 默认 **5173**（`frontend/vite.config.ts`），后端 CORS 已允许 5173。

刷新看板数据：**强刷** `/eval`（Ctrl+F5），确保后端 8080 已启动。

---

## 6. 评测路径说明（与线上对话的差异）

| 路径 | 用途 | 特点 |
|------|------|------|
| `AgentOrchestrator.retrieve_for_eval` | 评测检索 | multi_hop 分路、SIM-RAG、abstention；**不走 CRAG 拒答** |
| `RAGService.generate` → `generate_stream` | 评测生成 / 线上对话（**默认完整链路**） | CRAG、一致性双路、Post-hoc Guard |
| 线上对话 + `fast_mode=true` | 仅用户对话请求 | 见下「快速模式」 |

### 快速模式（与评测无关）

AI 对话页开关 → 请求体 `fast_mode` → `chat_runtime.fast_mode_context`（**单次 SSE 请求内** ContextVar，不改 `.env`、不影响评测脚本）。

| 快速模式 | 完整模式（评测 / 关开关） |
|----------|---------------------------|
| 关闭 Cross-Encoder、Post-hoc、答案一致性 | 按 `.env` 启用上述链路 |
| `AGENT_MAX_ROUNDS=1` | 默认 2 轮 |
| 保留 SIM-RAG、图谱 multi_hop、CRAG | 同上 |

**说明**：基线 KPI 以 `eval_baseline_report.json` 为准；需要完整质量链路时关闭快速模式；需要更快响应并保留 SIM-RAG / 图谱标签时可开启。

因此：**检索指标**与**生成指标**可能脱节（召回高但 AR 低），改善见 [RAG_IMPROVEMENT_ROADMAP.md §Week 3–4](RAG_IMPROVEMENT_ROADMAP.md#week-34--分块与生成质量包后续优先)。

---

## 7. 改造 backlog（评测体系）

| 优先级 | 项 | 状态 |
|--------|-----|------|
| P0 | 双轨命名 + MRR/NDCG + 分维度报告 | ✅ |
| P0 | v2 数据集草案 | ✅ |
| P1 | v2 人工抽检定稿 | 进行中 |
| P2 | 评估历史趋势图（前端） | 待做 |
| P3 | CI 全量 RAGAS 分层抽检 | Week 5+ |

---

## 8. 常见问题

**Q：CP-chunk 25% 和 RAGAS precision 72% 为何差很多？**  
A：计算方式不同；参见 §3 表格解释，以 CP-chunk 反映 top-k 噪声。

**Q：重跑评测后 Dashboard 数字变了？**  
A: 正常；`eval_baseline_report.json` 被覆盖。发布前固定一份报告并备份 JSON。

**Q：v1 与 v2 哪个用于基线 KPI？**  
A：默认以 **v1** 为准（召回/命中/NRR 更稳）；v2 用于 multi_hop 等专项诊断与改进跟踪。
