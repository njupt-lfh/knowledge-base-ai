# ADR-008: Token 与效率优化（Phase 2.3）

**状态**：已采纳  
**日期**：2026-05-26

## 决策

| 策略 | 实现 |
|------|------|
| 上下文压缩 | Phase 2.1 `compress_context`（保留） |
| 历史 summary memory | `history_memory_service.compress_history`：旧轮次 extractive 摘要 + 保留最近 2 轮 |
| Self-RAG 跳过闲聊 | Phase 2.2 Router（保留） |
| 增量 FTS 索引 | `sync_fts_incremental` 替代每次启动全量 DELETE+INSERT |
| Embedding 缓存 | `EmbeddingCache` LRU + `embed_documents` 去重 |
| Prompt caching（火山） | 暂不接入，依赖服务端能力，后续可选 |

## 关键文件

- `backend/app/services/embedding_cache.py`
- `backend/app/services/history_memory_service.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/fts_service.py` → `sync_fts_incremental`
- `backend/app/core/fts_init.py`
- `backend/app/services/agent_orchestrator.py` → 使用 `compress_history`

## 验收

```bash
cd backend
python scripts/verify_phase2_3.py
python -m pytest tests/test_token_efficiency.py -v
python -m pytest tests/ -q
```

## 配置

- `HISTORY_RECENT_TURNS`（默认 2）
- `HISTORY_SUMMARY_MAX_CHARS`（默认 600）
- `EMBEDDING_CACHE_SIZE`（默认 512）
- `FTS_INCREMENTAL_SYNC`（默认 true）
