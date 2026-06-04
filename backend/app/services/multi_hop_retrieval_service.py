"""多跳检索增强（Phase 3b P0：双 anchor 分路 + 引号片段 FTS）。

职责：
    - G-L1 anchor 拆分为子查询，各路独立检索再 RRF 融合
    - 「…」引号内文本 FTS 直连 chunk（v2 评测模板）
    - 供 AgentOrchestrator 评测与生产路径共用

在流水线中的位置：
    AgentOrchestrator._retrieve_enhanced → try_multi_hop_split_retrieve
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.chunk import Chunk
from .cross_encoder_rerank_service import cross_encoder_rerank
from .hybrid_retriever import merge_source_lists
from .post_retrieval_filter import apply_post_retrieval_filter
from .query_router import QueryRoute, decompose_multi_hop_query
from .retrieval_gate import apply_retrieval_abstention

logger = logging.getLogger(__name__)


class RetrieveFn(Protocol):
    async def __call__(
        self,
        db: AsyncSession,
        kb_id: str,
        query: str,
        *,
        route: QueryRoute,
        top_k: int,
        graph_mode: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...


_QUOTE_SPAN_RE = re.compile(r"「([^」]+)」")


def extract_quote_anchors(query: str) -> list[str]:
    """提取 query 中「」引号内的 chunk 锚点片段。"""
    spans = [s.strip() for s in _QUOTE_SPAN_RE.findall(query or "") if len(s.strip()) >= 2]
    deduped: list[str] = []
    seen: set[str] = set()
    for s in spans:
        key = s[:80]
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped[:3]


_ANCHOR_STOP = frozenset(
    {
        "综合两段内容",
        "之间有什么联系",
        "有何关联",
        "通过提升",
        "通过属于",
        "通过存在",
        "通过承担",
        "通过包含",
        "通过导致",
        "通过教导",
        "通过是",
        "通过频率",
        "通过缓解方式",
        "通过由",
        "引起",
        "关系",
        "联系",
        "关联",
        "论文",
        "技术",
        "小时",
        "个月",
        "周龄",
        "版本",
        "文档编号",
    }
)


def _clean_anchors(candidates: list[str]) -> list[str]:
    """去重并剔除噪声 anchor。"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        a = raw.strip()
        if len(a) < 2 or a in _ANCHOR_STOP or a in seen:
            continue
        seen.add(a)
        out.append(a)
    return out[:5]


def get_multi_hop_anchors(query: str) -> list[str]:
    """优先引号内片段，其次 G-L1 规则分解。"""
    quotes = extract_quote_anchors(query)
    if len(quotes) >= 2:
        return _clean_anchors(quotes)
    return _clean_anchors(decompose_multi_hop_query(query))


def should_use_multi_hop_split(route: QueryRoute, query: str) -> bool:
    """relational/comprehensive 且能拆出 ≥2 anchor 时启用双路检索。"""
    if not getattr(settings, "MULTI_HOP_SPLIT_ENABLED", True):
        return False
    if route not in ("relational", "comprehensive"):
        return False
    if not any(k in query for k in ("关联", "两段", "多跳", "之间", "关系", "联系")):
        return False
    return len(get_multi_hop_anchors(query)) >= 2


def _anchor_sub_query(anchor: str, original_query: str) -> str:
    """将 anchor 扩展为利于 Hybrid/FTS 召回的子问句。"""
    a = anchor.strip()
    if len(a) >= 12:
        return a
    if "通过" in original_query and a in original_query:
        return f"{a} {original_query[original_query.find(a) : original_query.find(a) + 40]}"
    return f"{a} 相关内容"


def _fts_search_variants(text: str) -> list[str]:
    """长实体/书名生成多组 FTS 查询（含截断与去书名号）。"""
    t = text.strip()
    if not t:
        return []
    variants: list[str] = []
    seen: set[str] = set()

    def add(q: str) -> None:
        q = q.strip()
        if len(q) < 2 or q in seen:
            return
        seen.add(q)
        variants.append(q)

    add(t)
    if len(t) > 24:
        add(t[:24])
        add(t[:40])
    stripped = re.sub(r"[《》「」『』\"'（）()]", " ", t)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if stripped and stripped != t:
        add(stripped)
    latin = re.findall(r"(?a)[A-Za-z][\w.-]{1,20}", t)
    for w in latin[:4]:
        add(w)
    return variants[:5]


def merge_multi_hop_with_quota(
    lists: list[list[dict[str, Any]]],
    *,
    top_k: int,
    quota_lists: list[list[dict[str, Any]]] | None = None,
    min_per_list: int = 1,
) -> list[dict[str, Any]]:
    """每路 anchor 先保留 min_per_list，再 RRF 填满 top_k（提升双 chunk 进 top-5）。"""
    if not lists:
        return []
    quota_lists = quota_lists or lists
    reserved: list[dict[str, Any]] = []
    reserved_ids: set[str] = set()

    for lst in quota_lists:
        if not lst:
            continue
        for item in lst[:min_per_list]:
            cid = item["chunk_id"]
            if cid in reserved_ids:
                continue
            reserved_ids.add(cid)
            reserved.append(dict(item))

    if len(reserved) >= top_k:
        return reserved[:top_k]

    pool = merge_source_lists(lists, top_k=top_k + len(reserved))
    for item in pool:
        cid = item["chunk_id"]
        if cid in reserved_ids:
            continue
        reserved_ids.add(cid)
        reserved.append(item)
        if len(reserved) >= top_k:
            break
    return reserved[:top_k]


async def _load_chunk_sources(
    db: AsyncSession,
    kb_id: str,
    chunk_ids: list[str],
    *,
    source: str,
) -> list[dict[str, Any]]:
    if not chunk_ids:
        return []
    chunks = (
        (
            await db.execute(
                select(Chunk).where(
                    Chunk.id.in_(chunk_ids),
                    Chunk.knowledge_base_id == kb_id,
                    Chunk.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    chunk_map = {c.id: c for c in chunks}
    sources: list[dict[str, Any]] = []
    for i, cid in enumerate(chunk_ids):
        chunk = chunk_map.get(cid)
        if not chunk:
            continue
        sources.append(
            {
                "chunk_id": cid,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "document_id": chunk.document_id,
                "score": round(1.0 - i * 0.04, 4),
                "source": source,
            }
        )
    return sources


async def retrieve_anchor_fts_chunks(
    db: AsyncSession,
    kb_id: str,
    anchor: str,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """单 anchor 多 variant FTS，不经 abstention（补 kg 空检索）。"""
    from .fts_service import search_fts

    chunk_ids: list[str] = []
    seen: set[str] = set()
    for variant in _fts_search_variants(anchor):
        try:
            hits = await search_fts(db, kb_id, variant, limit=limit)
        except Exception as exc:
            logger.debug("anchor FTS failed: %s", exc)
            continue
        for cid, _score in hits:
            if cid not in seen:
                seen.add(cid)
                chunk_ids.append(cid)
        if len(chunk_ids) >= limit:
            break
    return await _load_chunk_sources(db, kb_id, chunk_ids[:limit], source="anchor-fts")


async def retrieve_quote_anchor_chunks(
    db: AsyncSession,
    kb_id: str,
    query: str,
    *,
    limit_per_span: int | None = None,
) -> list[dict[str, Any]]:
    """对引号内片段做 FTS，直接召回对应 chunk。"""
    if not getattr(settings, "QUOTE_ANCHOR_FTS_ENABLED", True):
        return []

    spans = extract_quote_anchors(query)
    if not spans:
        return []

    from .fts_service import search_fts

    per = limit_per_span or int(getattr(settings, "QUOTE_ANCHOR_FTS_LIMIT_PER_SPAN", 3))
    chunk_ids: list[str] = []
    seen: set[str] = set()
    for span in spans:
        for variant in _fts_search_variants(span):
            try:
                hits = await search_fts(db, kb_id, variant[:120], limit=per)
            except Exception as exc:
                logger.debug("quote anchor FTS failed: %s", exc)
                continue
            for cid, _score in hits:
                if cid not in seen:
                    seen.add(cid)
                    chunk_ids.append(cid)
            if len(chunk_ids) >= per * len(spans):
                break

    return await _load_chunk_sources(db, kb_id, chunk_ids, source="quote-fts")


async def _multi_hop_fts_fallback(
    db: AsyncSession,
    kb_id: str,
    query: str,
    anchors: list[str],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    """空检索兜底：仅 quote-fts + 各 anchor-fts，不做 abstention。"""
    lists: list[list[dict[str, Any]]] = []
    quote = await retrieve_quote_anchor_chunks(db, kb_id, query)
    if quote:
        lists.append(quote)
    for anchor in anchors[:5]:
        fts = await retrieve_anchor_fts_chunks(db, kb_id, anchor)
        if fts:
            lists.append(fts)
    if not lists:
        return []
    quota = lists[1:] if quote else lists
    return merge_multi_hop_with_quota(
        lists,
        top_k=top_k,
        quota_lists=quota or lists,
        min_per_list=int(getattr(settings, "MULTI_HOP_ANCHOR_QUOTA_MIN", 1)),
    )


async def try_multi_hop_split_retrieve(
    db: AsyncSession,
    kb_id: str,
    query: str,
    *,
    route: QueryRoute,
    top_k: int,
    retrieve_fn: RetrieveFn,
    graph_mode: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """双 anchor 分路检索；无法拆分时返回 None。"""
    anchors = get_multi_hop_anchors(query)
    if len(anchors) < 2:
        return None

    per_k = int(getattr(settings, "MULTI_HOP_PER_ANCHOR_TOP_K", 5))
    quota_min = int(getattr(settings, "MULTI_HOP_ANCHOR_QUOTA_MIN", 1))
    fallback_on = getattr(settings, "MULTI_HOP_EMPTY_FALLBACK_ENABLED", True)

    all_lists: list[list[dict[str, Any]]] = []
    anchor_lists: list[list[dict[str, Any]]] = []
    graph_paths: list[dict[str, Any]] = []
    seen_path_keys: set[str] = set()

    quote_sources = await retrieve_quote_anchor_chunks(db, kb_id, query)
    if quote_sources:
        all_lists.append(quote_sources)

    for anchor in anchors[:5]:
        sub_q = _anchor_sub_query(anchor, query)
        sources, paths = await retrieve_fn(
            db,
            kb_id,
            sub_q,
            route=route,
            top_k=per_k,
            graph_mode=graph_mode,
        )
        fts_extra = await retrieve_anchor_fts_chunks(db, kb_id, anchor, limit=3)
        combined = merge_source_lists(
            [lst for lst in (sources, fts_extra) if lst],
            top_k=per_k,
        )
        if combined:
            anchor_lists.append(combined)
            all_lists.append(combined)
        for p in paths or []:
            key = str(p)
            if key not in seen_path_keys:
                seen_path_keys.add(key)
                graph_paths.append(p)

    if not all_lists:
        if fallback_on:
            merged = await _multi_hop_fts_fallback(
                db,
                kb_id,
                query,
                anchors,
                top_k=top_k,
            )
            return (merged, graph_paths) if merged else None
        return None

    pool_k = min(top_k + len(anchors) * 2, 15)
    merged = merge_multi_hop_with_quota(
        all_lists,
        top_k=pool_k,
        quota_lists=anchor_lists or all_lists,
        min_per_list=quota_min,
    )

    if getattr(settings, "CROSS_ENCODER_RERANK_ENABLED", False) and merged:
        pool = min(len(merged), getattr(settings, "HYBRID_RRF_POOL_SIZE", 30))
        merged = cross_encoder_rerank(query, merged, top_k=pool)
        merged = apply_post_retrieval_filter(merged, allow_soft_fallback=True)
        merged = merged[:top_k]
    else:
        merged = merged[:top_k]

    if not merged and fallback_on:
        merged = await _multi_hop_fts_fallback(db, kb_id, query, anchors, top_k=top_k)
        if merged:
            return merged, graph_paths

    if not merged:
        return None

    # 双路合并后各 chunk 往往只覆盖一个实体；放宽锚点「单 chunk 双命中」门控
    merged = apply_retrieval_abstention(
        query,
        merged,
        route,
        graph_paths=graph_paths,
        multi_hop_relaxed=True,
        ce_min_score=0.25,
    )
    if not merged and fallback_on:
        merged = await _multi_hop_fts_fallback(db, kb_id, query, anchors, top_k=top_k)
        if merged:
            return merged, graph_paths
    if not merged:
        return None
    return merged, graph_paths


def diagnose_retrieval_hits(
    relevant_ids: set[str],
    retrieved_ids: list[str],
) -> dict[str, Any]:
    """统计 0/1/2 命中（评测集 relevant 常为 2 条）。"""
    hits = [cid for cid in retrieved_ids if cid in relevant_ids]
    n_rel = len(relevant_ids)
    n_hit = len(hits)
    if n_rel == 0:
        bucket = "n/a"
    elif n_hit >= n_rel:
        bucket = "full"
    elif n_hit == 1:
        bucket = "partial"
    else:
        bucket = "miss"
    return {
        "relevant_count": n_rel,
        "hit_count": n_hit,
        "hit_ids": hits,
        "bucket": bucket,
    }
