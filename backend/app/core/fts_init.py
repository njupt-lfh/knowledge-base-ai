"""FTS5 初始化（在 init_db 时调用）"""

from __future__ import annotations

import logging

from ..core.config import settings
from ..services.fts_service import backfill_fts, ensure_fts_schema, sync_fts_incremental

logger = logging.getLogger(__name__)


async def init_fts_on_connection(conn) -> None:
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
