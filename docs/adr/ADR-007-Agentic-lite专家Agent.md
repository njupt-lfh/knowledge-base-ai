# ADR-007: Agentic-lite 专家 Agent（Phase 2.2）

**状态**：已采纳  
**日期**：2026-05-26

## 决策

- 新增 `AgentOrchestrator`：Query Router → Hybrid Retrieve → CRAG-lite → Generate / Refusal
- **Query Router**（规则）：`factual` / `relational` / `comprehensive` / `chitchat`，无额外 LLM 调用
- **CRAG-lite**：检索分 + 词项重叠联合判定；不足则最多 **2 轮**重试（放宽 query / top_k）
- **拒答**：两轮仍不足 → 固定拒答话术 + 空/弱 sources → `GapService.process_after_chat` 入队
- **闲聊 Self-RAG**：跳过检索，独立 system prompt
- 关系型问题 Phase 3 前仍走 Hybrid fallback（加大 top_k），图谱检索后续接入

## 关键文件

| 模块 | 文件 |
|------|------|
| Router | `backend/app/services/query_router.py` |
| CRAG | `backend/app/services/crag_evaluator.py` |
| Agent | `backend/app/services/agent_orchestrator.py` |
| RAG 入口 | `backend/app/services/rag_service.py` |
| 检索测试 | `backend/app/services/chunk_service.py` |

## 验收

```bash
cd backend
python scripts/verify_phase2_2.py
python -m pytest tests/test_agent_orchestrator.py -v
python -m pytest tests/ -q
```

## 后续（Phase 2.3+）

- 历史 summary memory、Embedding 缓存、增量索引
- DeepEval CI（Phase 2.4）
- Phase 3 关系型问题接入轻量图谱检索
