# RAG 评测指标改善路线图

> **文档版本**：v1.1  
> **更新日期**：2026-06-04  
> **适用项目**：`knowledge-base-ai`  
> **关联**：[评测体系说明](EVAL.md) · [ADR-000](adr/ADR-000-评测体系.md) · [架构文档](ARCHITECTURE.md)

项目实施、验收口径与 CI 门禁以本文为准。

---

## 1. 执行摘要

系统在 **召回侧已较强**，短板集中在 **chunk 级精确率、RAGAS 答案相关性、误拒答导致的生成质量** 与 **端到端延迟**。

| 指标 | 基线（2026-05） | 健康参考 | Week 2 目标 | Week 5+ 目标 |
|------|----------------------|----------|-------------|--------------|
| **CP-chunk**（chunk 级精确率） | 0.255 | ≥ 0.45 | **≥ 0.40** | 0.45–0.52 |
| **答案相关性**（RAGAS AR） | 0.442 | ≥ 0.60 | ≥ 0.55 | 0.58–0.65 |
| **忠实度**（RAGAS FA） | 0.739 | ≥ 0.80 | ≥ 0.78 | ≥ 0.82 |
| **负例拒答率 NRR** | 0.60 | ≥ 0.85 | ≥ 0.82 | ≥ 0.85 |
| **CR-chunk**（召回） | 0.885 | ≥ 0.80 | ≥ 0.85 | ≥ 0.85 |
| **检索命中率** | 0.956 | ≥ 0.90 | ≥ 0.93 | ≥ 0.93 |
| **平均生成时延** | ~16.7s | ≤ 8s | ~14s | **6–9s** |

**核心结论（评测与代码交叉验证）**：

1. 精确率低的主因是 **top-k 噪声** + **轻量 Rerank 语义不足** + **v1 单 relevant 标注在 top_k=5 下的数学上限（0.2）**，而非「完全找不到」。
2. **负例 abstention 过松**（早期 `CRAG_MIN_SCORE=0.04`）导致无关问题仍返回检索结果。
3. **Post-hoc Answer Guard + CRAG 拒答** 提升忠实度，但易 **误拒答**，拉低 RAGAS `answer_relevancy`。
4. **评测集 v1 模板化** 放大噪声；需 **v2 自然问法 + 多 relevant 标注** 并行建设（见 [EVAL.md](EVAL.md)）。

---

## 2. 指标口径（答辩必讲）

| 简称 | 含义 | 计算位置 |
|------|------|----------|
| **CP-chunk** / **CR-chunk** | chunk 级精确率 / 召回率 | `retrieval_metrics.py`：\|rel∩ret\|/\|ret\|、\|rel∩ret\|/\|rel\| |
| **CP-ragas** / **CR-ragas** | RAGAS 上下文精确 / 召回 | `ragas_runner.py`（LLM 判别，常与 chunk 级差异大） |
| **FA / AR** | 忠实度 / 答案相关性 | RAGAS，需 `--ragas` 全量评测 |
| **NRR** | 负例拒答率 | 负例样本空检索比例 |
| **MRR / NDCG@5** | 排序质量 | 仅正例；见 `retrieval_metrics.py` |

> **chunk 级 CP（~0.25–0.52）≠ RAGAS CP（~0.72–0.78）**。答辩必须说明双轨口径，避免被质疑「数字矛盾」。

---

## 3. 项目当前进度（截至 2026-06-04）

| 阶段 | 内容 | 状态 | 说明 |
|------|------|------|------|
| **Week 0** | Prompt 拒答约束 + Post-hoc Guard + Abstention 校准 | ✅ | v1 上 NRR=1.0、CR≈0.91（retrieval-only） |
| **Week 1–2** | Cross-Encoder 重排 + 检索后过滤 + 动态 top_k | ✅ 代码已接入 | `cross_encoder_rerank_service.py`、`post_retrieval_filter.py` |
| **Week 1–2** | 评测 v2 草案 + 双轨报告 + 分维度 Dashboard | ✅ | `eval_qa_dataset_v2.json`、`aggregate.py`、`/eval` |
| **Phase 3** | 轻量图谱 + multi_hop 分路 + Phase3 出口 | ⚠️ 部分达标 | v1 回归 PASS；v2 multi_hop CR≈0.59（目标 0.82） |
| **Week 3–4** | 结构分块 re-index + Prompt 分层 + 证据抽取 | 📋 待做 | 见 §5 |
| **Week 5+** | CRAG 早停 + HNSW + CI RAGAS 抽检 | 📋 待做 | 见 §6 |

**近期 v1 全量评测快照**（`eval_baseline_report.json`，答辩展示以该文件为准）：

| 指标 | 约值 |
|------|------|
| CR-chunk | 0.87 |
| 检索命中率 | 0.90 |
| CP-chunk | 0.51–0.67（随 Cross-Encoder / 报告版本） |
| NRR | 1.0 |
| FA（RAGAS） | 0.71–0.84 |
| AR（RAGAS） | 受误拒答影响，需 Week 3–4 Prompt/路由优化 |

---

## 4. 实施路线

### Week 0 — 快速见效包（已完成）

| 项 | 做法 | 关键文件 |
|----|------|----------|
| Q0-1 | 强化 system prompt + Post-hoc 自检 | `rag_service.py`、`answer_guard_service.py` |
| Q0-2 | Abstention 锚点词 + 阈值校准 | `retrieval_gate.py`、`crag_evaluator.py` |

**验收命令**：

```bash
cd backend
python scripts/run_rag_eval.py --dataset v1 --retrieval-only --limit 0
```

---

### Week 1–2 — 检索精确率核心包（进行中 / 大部分已落地）

| 项 | 做法 | 预期收益 |
|----|------|----------|
| **C1** Cross-Encoder 二阶段重排 | Hybrid top-30 → CE → top 3–4 | CP-chunk +0.12~0.18 |
| **C2** 检索后硬过滤 + 同文档去重 | τ 过滤、每文档最多 2 条 | CP +0.06~0.10 |
| **C3** 动态 top_k（按 QueryRoute） | factual=3、multi_hop=5 等 | fact precision +0.04~0.08 |
| **C4** 评测 v2 | 保留 v1 回归，v2 自然问法 + 多 relevant | 可解释、可分层 |

**验收**：

```bash
python scripts/run_rag_eval.py --dataset v1 --retrieval-only --limit 0
python scripts/run_rag_eval.py --dataset v2 --retrieval-only --limit 0
python scripts/run_phase3_exit.py --report-only
```

---

### Week 3–4 — 分块与生成质量包（答辩后优先）

> **主线**：在不动召回的前提下，抬 **AR ≥ 0.55**、**FA ≥ 0.80**。

| 项 | 做法 | 说明 |
|----|------|------|
| **G1** 结构感知分块 | 按标题/页分段，800 字上限 | **优先于** Sentence Window（二选一） |
| **G2** Prompt 分层 | 1 句答案 + ≤3 要点 + 强制 [来源 N] | 减少冗长复述 |
| **G3** Extract-then-Generate | 先抽 2–3 句证据再生成 | 降噪声 |
| **G4** Lost-in-the-Middle | 高分 chunk 放 context 首尾 | 低成本 |
| **G5** 精准 SIM-RAG | **仅 multi_hop** 启用，PruneRAG 式剪枝 | 避免 fact 题误伤 |

**里程碑**：CP-chunk ≥ 0.45；AR ≥ 0.55；multi_hop CR ≥ 0.88（v2）。

**含 RAGAS 全量**：

```bash
python scripts/run_rag_eval.py --dataset v1 --limit 0 --ragas
```

结构分块后需对目标库 **re-index**（`reprocess` / 重建 Chroma），再复跑评测。

---

### Week 5+ — 性能与 CI（工程化收尾）

| 项 | 做法 | 预期 |
|----|------|------|
| **P1** CRAG 单轮早停 | 第 1 轮充分则跳过第 2 轮 | 延迟 −40~50% |
| **P2** Chroma HNSW 调参 | M / ef_search 等 | 检索 ~1.3s → 0.3–0.5s |
| **P3** HyDE（可选 A/B） | 仅短 query / concept | 与降延迟冲突，后置 |
| **CI** | `run_rag_eval --ci-mode` + 分层 RAGAS 抽检 | 见 `app/eval/ci_gates.py` |

---

## 5. Phase 4 / 5 与路线图关系

| 项目阶段 | 内容 | 与路线图对应 |
|----------|------|----------------|
| **Phase 4**（能力） | 多模态入库、PDF 内嵌图、SIM-RAG、文件夹同步 | ADR-011～014；SIM-RAG 对齐 **G5** |
| **Phase 4**（评测） | RAGAS 全量 + 结构分块 re-index | **Week 3–4 G1 + RAGAS** |
| **Phase 5** | 性能优化 + CI 自动化 | **Week 5+ P1/P2/CI** |

**建议顺序**：Week 3–4（质量）与 Phase 4 评测/re-index 合并推进；Phase 5 性能与 CI 在 v1 回归稳定后接入。

---

## 6. 答辩话术参考

### 「精确率为什么不高？」

> 我们区分 **CP-chunk**（top-k 中相关 chunk 占比）与 **CP-ragas**（LLM 加权）。召回与命中率已在 0.85–0.90 档，说明覆盖够；CP-chunk 低反映 **同主题噪声 chunk** 与 **轻量重排语义不足**。已落地 Cross-Encoder、检索后过滤与动态 top_k，并规划结构分块，目标 chunk 级 **0.45–0.50**。

### 「答案相关性为什么低？」

> RAGAS 答案相关性衡量 **回答是否对准问题**。线上 **CRAG + Post-hoc Guard** 偏保守，存在「检索已有 context 仍拒答」的情况，会显著拉低 AR。Week 3–4 将通过 **多跳专用 prompt、减少误拒答、证据抽取** 优化；评测口径见 [EVAL.md](EVAL.md) 双轨说明。

### 「为什么慢？」

> 延迟主要来自 **两轮 CRAG 检索 + 串行 LLM**。Week 5+ 计划 **CRAG 早停** 与 **HNSW 调参**，目标端到端 **6–9s**，且不牺牲已提升的检索质量。

### 「多跳 / Agent 效果？」

> Phase 3 显示盲目 SIM-RAG 可能伤 fact 题。路线图为 **仅 multi_hop 走图谱分路与精准 SIM-RAG**；v2 multi_hop 召回仍在提升中（当前约 0.59，目标 0.82 为拉伸线，汇报时可强调 **0.6–0.7 + v1 回归 PASS**）。

---

## 7. 里程碑与附录 A（实测填写）

| 完成日期 | 阶段 | CP-chunk | AR | FA | NRR | 备注 |
|----------|------|----------|-----|-----|-----|------|
| 2026-05-28 | 基线 | 0.255 | 0.442 | 0.739 | 0.60 | 初始基线 |
| 2026-06-02 | Week 0 | ~0.28 | — | — | **1.0** | v1 retrieval-only |
| 2026-06-04 | Week 1–2 | ~0.51 | ~0.41* | ~0.84* | 1.0 | *全量 `--ragas`；AR 待 G2/G5 |
| | Week 3–4 | | | | | |
| | Week 5+ | | | | | |

每完成一阶段：更新上表、`data/eval_baseline_report*.json`，并视需要更新 `frontend/src/data/evalPhaseComparison.ts` 静态快照。

---

## 8. 参考文献与 ADR

- 检索重排：[BGE-Reranker v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- 多跳剪枝：PruneRAG（WWW 2026）
- 本项目：[ADR-006](adr/ADR-006-Hybrid检索升级.md)、[ADR-007](adr/ADR-007-Agentic-lite专家Agent.md)、[ADR-010](adr/ADR-010-轻量知识图谱.md)、[ADR-013](adr/ADR-013-SIM-RAG多轮检索.md)

**文档维护**：修改验收阈值或实施顺序时，同步更新 [EVAL.md](EVAL.md)、`ci_gates.py` 与 README 中的评测章节。
