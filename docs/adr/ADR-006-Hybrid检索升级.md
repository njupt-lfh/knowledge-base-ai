# ADR-006: Hybrid 检索升级（Phase 2.1）

**状态**：已采纳  
**日期**：2026-05-26

## 决策

- `HybridRetriever`：Chroma 向量 + SQLite FTS5 BM25 → RRF(k=60) → 轻量 Rerank → 质量分融合
- FTS5 表 `chunks_fts`，`init_db` 时 backfill；chunk 写入/更新/入库时同步
- 动态 `top_k`（3–10）；context extractive 压缩（默认 4500 字符）
- Rerank 采用词项重叠 + RRF 融合（无额外 Cross-Encoder 模型依赖，延迟 < 500ms）

## 验收

```bash
cd backend
python scripts/verify_phase2_1.py
python -m pytest tests/test_hybrid_retriever.py tests/test_fts_service.py -v
```

## 后续（Phase 2.2+）

- Agentic-lite 状态机、CRAG-lite、Query Router
- 可选接入真实 Cross-Encoder 或火山 Rerank API
