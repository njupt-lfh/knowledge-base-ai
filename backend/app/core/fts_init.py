"""FTS5 全文检索索引初始化。

在 `init_db()` 建表完成后调用，负责创建 FTS5 虚拟表并对 chunk 内容做
首次回填或增量同步，为 Hybrid 检索中的关键词召回提供索引基础。
"""

from __future__ import annotations

import logging

from ..core.config import settings
from ..services.fts_service import backfill_fts, ensure_fts_schema, sync_fts_incremental

logger = logging.getLogger(__name__)


async def init_fts_on_connection(conn) -> None:
    """在给定数据库连接上初始化 FTS5 并同步 chunk 索引。

    参数:
        conn: SQLAlchemy 异步连接，通常来自 `init_db` 的 begin 上下文。

    逻辑:
        若 FTS 表刚创建则全量回填；否则按配置选择增量同步或全量回填。
    """
    created = await ensure_fts_schema(conn)
    if created:
        count = await backfill_fts(conn)
        logger.info("init_db: FTS5 initial backfill %d chunks", count)
        return

    if getattr(settings, "FTS_INCREMENTAL_SYNC", True):
        count = await sync_fts_incremental(conn)
        logger.info("init_db: FTS5 incremental sync %d rows", count)
    else:
        count = await backfill_fts(conn)
        logger.info("init_db: FTS5 full backfill %d chunks", count)
