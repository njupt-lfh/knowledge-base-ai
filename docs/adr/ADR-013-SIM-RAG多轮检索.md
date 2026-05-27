# ADR-013：SIM-RAG 多轮检索（Phase 4.3）

## 状态

已接受（2026-05-24）

## 决策

在 Agentic-lite 既有 2 轮 CRAG 之上，对 **综合型/多问句** 启用 SIM-RAG：

1. **子问题拆分**（规则，无 LLM）：按 `？；;` 及「以及/并且/还有」切分，上限 `SIM_RAG_MAX_SUB_QUERIES`（默认 3）。
2. **并行多路检索**：每个子问题独立 Hybrid/Graph 检索，RRF 融合。
3. **覆盖度 Critic**：每个子问题需在来源中有词重叠（`SIM_RAG_SUBQUERY_MIN_OVERLAP`），整体覆盖率 ≥ `SIM_RAG_MIN_COVERAGE` 且通过 CRAG-lite 才判充分。
4. **开关**：`SIM_RAG_ENABLED`；SSE `agent_meta` 增加 `sim_rag_used`、`sim_sub_queries`、`sim_coverage`。

## 验证

`python scripts/verify_phase4_3.py`

## 非目标

- 子问题 LLM 分解（省 token）
- 超过 3 轮检索循环
