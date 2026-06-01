"""SQLite FTS5 全文索引服务（Phase 2.1）。

职责：
    维护 chunks_fts 虚拟表，支持 BM25 关键词检索，
    与 Chroma 向量检索组成 Hybrid 双路。

在流水线中的位置：
    HybridRetriever.search → search_fts
    入库：document_service / chunk_service → upsert_chunk_fts

依赖：无（直接 SQL + SQLite FTS5）
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

FTS_TABLE = "chunks_fts"


async def ensure_fts_schema(conn) -> bool:
    """创建 FTS5 虚拟表（若不存在）。

    参数:
        conn: 数据库连接

    返回:
        True 表示本次新建，False 表示已存在
    """
    result = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": FTS_TABLE},
    )
    if result.first():
        return False
    await conn.execute(
        text(
            f"""
            CREATE VIRTUAL TABLE {FTS_TABLE} USING fts5(
                chunk_id UNINDEXED,
                knowledge_base_id UNINDEXED,
                content,
                tokenize='unicode61'
            )
            """
        )
    )
    logger.info("fts: created virtual table %s", FTS_TABLE)
    return True


async def sync_fts_incremental(conn) -> int:
    """增量同步：补缺失、删失效、更新内容变更的 chunk。

    参数:
        conn: 数据库连接

    返回:
        新增 + 刷新的行数
    """
    await conn.execute(
        text(
            f"""
            DELETE FROM {FTS_TABLE}
            WHERE chunk_id IN (
                SELECT f.chunk_id FROM {FTS_TABLE} AS f
                LEFT JOIN chunks c ON c.id = f.chunk_id
                WHERE c.id IS NULL OR c.is_active = 0
            )
            """
        )
    )
    inserted = (
        await conn.execute(
            text(
                f"""
                INSERT INTO {FTS_TABLE}(chunk_id, knowledge_base_id, content)
                SELECT c.id, c.knowledge_base_id, c.content
                FROM chunks c
                LEFT JOIN {FTS_TABLE} f ON f.chunk_id = c.id
                WHERE c.is_active = 1 AND f.chunk_id IS NULL
                """
            )
        )
    ).rowcount or 0

    stale = (
        await conn.execute(
            text(
                f"""
                SELECT f.chunk_id, c.knowledge_base_id, c.content
                FROM {FTS_TABLE} AS f
                INNER JOIN chunks c ON c.id = f.chunk_id
                WHERE c.is_active = 1 AND f.content != c.content
                """
            )
        )
    ).all()
    refreshed = 0
    for chunk_id, kb_id, content in stale:
        await conn.execute(
            text(f"DELETE FROM {FTS_TABLE} WHERE chunk_id = :cid"), {"cid": chunk_id}
        )
        await conn.execute(
            text(
                f"INSERT INTO {FTS_TABLE}(chunk_id, knowledge_base_id, content) "
                "VALUES (:cid, :kb, :content)"
            ),
            {"cid": chunk_id, "kb": kb_id, "content": content},
        )
        refreshed += 1
    return int(inserted) + refreshed


async def backfill_fts(conn) -> int:
    """全量重建 FTS 索引。

    参数:
        conn: 数据库连接

    返回:
        写入行数
    """
    await conn.execute(text(f"DELETE FROM {FTS_TABLE}"))
    result = await conn.execute(
        text(
            f"""
            INSERT INTO {FTS_TABLE}(chunk_id, knowledge_base_id, content)
            SELECT id, knowledge_base_id, content
            FROM chunks
            WHERE is_active = 1
            """
        )
    )
    return result.rowcount or 0


async def upsert_chunk_fts(
    db: AsyncSession, chunk_id: str, kb_id: str, content: str, *, active: bool = True
) -> None:
    """单 chunk FTS  upsert（先删后插）。

    参数:
        db: 异步会话
        chunk_id: chunk ID
        kb_id: 知识库 ID
        content: 索引正文
        active: 是否活跃（非活跃则只删除）
    """
    await db.execute(text(f"DELETE FROM {FTS_TABLE} WHERE chunk_id = :cid"), {"cid": chunk_id})
    if active and content.strip():
        await db.execute(
            text(
                f"INSERT INTO {FTS_TABLE}(chunk_id, knowledge_base_id, content) "
                "VALUES (:cid, :kb, :content)"
            ),
            {"cid": chunk_id, "kb": kb_id, "content": content},
        )


async def delete_chunk_fts(db: AsyncSession, chunk_id: str) -> None:
    """从 FTS 索引删除指定 chunk。

    参数:
        db: 异步会话
        chunk_id: chunk ID
    """
    await db.execute(text(f"DELETE FROM {FTS_TABLE} WHERE chunk_id = :cid"), {"cid": chunk_id})


def build_fts_query(query: str) -> str | None:
    """构造 FTS5 MATCH 表达式（中文单字 + 英文词 OR 组合）。

    参数:
        query: 用户查询

    返回:
        MATCH 字符串或 None（空查询）
    """
    text_q = query.strip()
    if not text_q:
        return None
    latin = [p for p in re.findall(r"\w{2,}", text_q, re.ASCII) if len(p) >= 2]
    cjk = re.findall(r"[\u4e00-\u9fff]", text_q)
    parts = (latin + cjk)[:20]
    if not parts:
        parts = [text_q[:32]]
    return " OR ".join(f'"{p}"' for p in parts)


async def search_fts(
    db: AsyncSession,
    kb_id: str,
    query: str,
    *,
    limit: int = 15,
) -> list[tuple[str, float]]:
    """BM25 检索，返回 (chunk_id, bm25_score)。

    参数:
        db: 异步会话
        kb_id: 知识库 ID
        query: 查询文本
        limit: 最大条数

    返回:
        (chunk_id, 分数) 列表，分数越高越相关（已对 bm25 负值取反）
    """
    match = build_fts_query(query)
    if not match:
        return []

    try:
        rows = (
            await db.execute(
                text(
                    f"""
                    SELECT f.chunk_id, bm25({FTS_TABLE}) AS score
                    FROM {FTS_TABLE} AS f
                    INNER JOIN chunks c ON c.id = f.chunk_id
                    WHERE {FTS_TABLE} MATCH :match
                      AND f.knowledge_base_id = :kb
                      AND c.is_active = 1
                    ORDER BY score
                    LIMIT :lim
                    """
                ),
                {"match": match, "kb": kb_id, "lim": limit},
            )
        ).all()
    except Exception as e:
        logger.warning("fts search failed: %s", e)
        return []

    out: list[tuple[str, float]] = []
    for chunk_id, score in rows:
        # bm25() 返回负值，绝对值越大越相关
        out.append((chunk_id, round(-float(score or 0), 6)))
    return out
