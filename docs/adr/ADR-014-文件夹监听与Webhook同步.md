# ADR-014：文件夹监听与 Webhook 同步（Phase 4.4）

## 状态

已接受（2026-05-24）

## 决策

1. **表** `kb_folder_watches`：kb_id、folder_path、enabled、recursive、last_scan_at。
2. **扫描**：比对源文件 mtime 与已入库副本；新增 import、变更 reset chunks 后重跑 `_process_document` / `_process_image`。
3. **API**（`/api/sync`）：
   - `POST /watches` 注册监听目录
   - `POST /watches/{id}/scan`、`POST /knowledge-bases/{kb_id}/scan`
   - `POST /webhook/{kb_id}`、`POST /scan-all`（可选 `X-Sync-Secret`）
4. **后台**：`SYNC_WATCH_ENABLED=true` 时按 `SYNC_WATCH_INTERVAL_SEC` 周期扫描（默认关闭）。

## 验证

`python scripts/verify_phase4_4.py`

## 非目标

- 双向同步、删除远端文件时自动删库内文档
- 全量 Celery 队列（仍用进程内 asyncio 循环）
