"""Phase 4 统计聚合 — 基于 Chunk / Message 真实数据"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..models.conversation import Conversation, Message


def _parse_sources(raw) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, dict)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return _parse_sources(parsed)
        except json.JSONDecodeError:
            return []
    return []


async def hit_distribution(db: AsyncSession, kb_id: str) -> list[dict]:
    rows = (await db.execute(
        select(Chunk.hit_count).where(Chunk.knowledge_base_id == kb_id)
    )).all()

    buckets = {"0次": 0, "1-5次": 0, "6-20次": 0, "20+次": 0}
    for (hits,) in rows:
        h = hits or 0
        if h == 0:
            buckets["0次"] += 1
        elif h <= 5:
            buckets["1-5次"] += 1
        elif h <= 20:
            buckets["6-20次"] += 1
        else:
            buckets["20+次"] += 1

    return [{"label": k, "count": v} for k, v in buckets.items()]


async def cite_vs_hit(db: AsyncSession, kb_id: str, limit: int = 10) -> list[dict]:
    cite_counts: dict[str, int] = defaultdict(int)

    msg_rows = (await db.execute(
        select(Message.sources)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.knowledge_base_id == kb_id,
            Message.role == "assistant",
            Message.sources.isnot(None),
        )
    )).all()

    for (sources_raw,) in msg_rows:
        for src in _parse_sources(sources_raw):
            cid = src.get("chunk_id")
            if cid:
                cite_counts[cid] += 1

    top_chunks = (await db.execute(
        select(Chunk.id, Chunk.content, Chunk.hit_count)
        .where(Chunk.knowledge_base_id == kb_id)
        .order_by(desc(Chunk.hit_count), desc(Chunk.created_at))
        .limit(limit)
    )).all()

    items = []
    for row in top_chunks:
        label = row.content[:24].replace("\n", " ")
        items.append({
            "chunk_id": row.id,
            "label": label,
            "hit_count": row.hit_count or 0,
            "cite_count": cite_counts.get(row.id, 0),
        })

    if not items and cite_counts:
        cited_ids = sorted(cite_counts.keys(), key=lambda x: cite_counts[x], reverse=True)[:limit]
        chunk_rows = (await db.execute(
            select(Chunk.id, Chunk.content, Chunk.hit_count).where(Chunk.id.in_(cited_ids))
        )).all()
        chunk_map = {r.id: r for r in chunk_rows}
        for cid in cited_ids:
            row = chunk_map.get(cid)
            if row:
                items.append({
                    "chunk_id": row.id,
                    "label": row.content[:24].replace("\n", " "),
                    "hit_count": row.hit_count or 0,
                    "cite_count": cite_counts[cid],
                })

    return items


async def rag_sankey(db: AsyncSession, kb_id: str, limit: int = 15) -> dict:
    assistant_rows = (await db.execute(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.knowledge_base_id == kb_id,
            Message.role == "assistant",
            Message.sources.isnot(None),
        )
        .order_by(desc(Message.created_at))
        .limit(limit)
    )).scalars().all()

    nodes: dict[str, str] = {}
    links_map: dict[tuple[str, str], float] = defaultdict(float)

    def add_node(nid: str, name: str) -> None:
        if nid not in nodes:
            nodes[nid] = name

    for amsg in assistant_rows:
        sources = _parse_sources(amsg.sources)
        if not sources:
            continue

        user_row = (await db.execute(
            select(Message)
            .where(
                Message.conversation_id == amsg.conversation_id,
                Message.role == "user",
                Message.created_at < amsg.created_at,
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )).scalar_one_or_none()

        q_text = (user_row.content if user_row else "用户提问")[:20].replace("\n", " ")
        a_text = amsg.content[:20].replace("\n", " ") or "AI 回答"
        q_id = f"q:{user_row.id if user_row else amsg.id}"
        a_id = f"a:{amsg.id}"

        add_node(q_id, f"问: {q_text}")
        add_node(a_id, f"答: {a_text}")

        for src in sources[:3]:
            cid = src.get("chunk_id")
            if not cid:
                continue
            content = (src.get("content") or "")[:18].replace("\n", " ")
            c_id = f"c:{cid}"
            add_node(c_id, f"块: {content}")
            links_map[(q_id, c_id)] += 1
            links_map[(c_id, a_id)] += float(src.get("score") or 1)

    return {
        "nodes": [{"name": nid, "label": label} for nid, label in nodes.items()],
        "links": [
            {"source": s, "target": t, "value": max(v, 0.1)}
            for (s, t), v in links_map.items()
        ],
    }


async def activity_heatmap(db: AsyncSession, kb_id: str | None = None, days: int = 30) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=max(1, min(days, 90)))

    query = (
        select(
            func.strftime("%w", Message.created_at).label("dow"),
            func.strftime("%H", Message.created_at).label("hour"),
            func.count(Message.id).label("cnt"),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.created_at >= since)
    )
    if kb_id:
        query = query.where(Conversation.knowledge_base_id == kb_id)

    query = query.group_by("dow", "hour")
    rows = (await db.execute(query)).all()

    # ECharts heatmap: [hour, dow, count] — dow 0=Sun, remap to Mon=0..Sun=6
    dow_map = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    result = []
    for dow_str, hour_str, cnt in rows:
        dow = dow_map.get(int(dow_str), 0)
        hour = int(hour_str)
        result.append({"dow": dow, "hour": hour, "count": int(cnt)})
    return result


async def cold_knowledge_count(db: AsyncSession, kb_id: str | None = None, days: int = 90) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = select(func.count(Chunk.id)).where(
        Chunk.hit_count == 0,
        Chunk.created_at <= cutoff,
    )
    total_query = select(func.count(Chunk.id)).where(Chunk.hit_count == 0)

    if kb_id:
        query = query.where(Chunk.knowledge_base_id == kb_id)
        total_query = total_query.where(Chunk.knowledge_base_id == kb_id)

    cold_old = (await db.execute(query)).scalar() or 0
    cold_all = (await db.execute(total_query)).scalar() or 0

    return {
        "cold_count_90d": int(cold_old),
        "cold_count_total": int(cold_all),
        "threshold_days": days,
    }


async def hit_trend(db: AsyncSession, kb_id: str | None = None, days: int = 7) -> list[dict]:
    """每日 RAG 引用趋势：统计当天带 sources 的 assistant 消息数（真实对话数据）"""
    days = max(1, min(days, 30))
    today = datetime.utcnow().date()
    points = []

    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())

        query = (
            select(func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.role == "assistant",
                Message.sources.isnot(None),
                Message.created_at >= day_start,
                Message.created_at <= day_end,
            )
        )
        if kb_id:
            query = query.where(Conversation.knowledge_base_id == kb_id)

        cnt = (await db.execute(query)).scalar() or 0
        points.append({"date": day.isoformat(), "hits": int(cnt)})

    return points
