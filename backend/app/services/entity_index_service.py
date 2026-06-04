"""LinearRAG 风格实体索引（Phase 3b 骨架）。

职责：
    从 kg_relations 构建 Entity→chunk 倒排与共现图；
    查询侧实体 linking → 一跳 chunk → 共现二跳扩展 → 轻量 PageRank 排序。

在流水线中的位置：
    GraphRetriever（GRAPH_MODE=linear）→ search_entity_index

依赖：
    - graph_store_service：load_relations、link_entities_in_query
    - query_router.decompose_multi_hop_query（linking 失败回退）
"""

from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.chunk import Chunk
from ..models.kg_relation import KgRelation
from .graph_store_service import link_entities_in_query, load_relations
from .multi_hop_retrieval_service import get_multi_hop_anchors

logger = logging.getLogger(__name__)

_INDEX_CACHE: OrderedDict[str, EntityIndexSnapshot] = OrderedDict()
_CACHE_MAX = 8

_GRAPH_MODE_CHOICES = frozenset({"lite", "linear", "legacy"})


def normalize_graph_mode(mode: str | None) -> str:
    """校验并归一化 GRAPH_MODE。"""
    m = (mode or getattr(settings, "GRAPH_MODE", "lite") or "lite").lower().strip()
    if m not in _GRAPH_MODE_CHOICES:
        logger.warning("unknown GRAPH_MODE=%s, fallback to lite", m)
        return "lite"
    return m


@dataclass
class EntityIndexSnapshot:
    """知识库实体倒排与共现邻接（内存快照）。"""

    kb_id: str
    entity_to_chunks: dict[str, set[str]] = field(default_factory=dict)
    chunk_to_entities: dict[str, set[str]] = field(default_factory=dict)
    chunk_to_document: dict[str, str] = field(default_factory=dict)
    cooccurrence: dict[str, set[str]] = field(default_factory=dict)
    entity_names: list[str] = field(default_factory=list)


def invalidate_entity_index_cache(kb_id: str) -> None:
    """三元组/索引变更后使实体索引缓存失效。"""
    _INDEX_CACHE.pop(kb_id, None)


def _cache_get(kb_id: str) -> EntityIndexSnapshot | None:
    snap = _INDEX_CACHE.get(kb_id)
    if snap is not None:
        _INDEX_CACHE.move_to_end(kb_id)
    return snap


def _cache_set(snap: EntityIndexSnapshot) -> None:
    _INDEX_CACHE[snap.kb_id] = snap
    _INDEX_CACHE.move_to_end(snap.kb_id)
    while len(_INDEX_CACHE) > _CACHE_MAX:
        _INDEX_CACHE.popitem(last=False)


def _add_entity_chunk(
    snap: EntityIndexSnapshot,
    entity: str,
    chunk_id: str,
    document_id: str,
) -> None:
    name = entity.strip()
    if len(name) < 2:
        return
    snap.entity_to_chunks.setdefault(name, set()).add(chunk_id)
    snap.chunk_to_entities.setdefault(chunk_id, set()).add(name)
    snap.chunk_to_document[chunk_id] = document_id


def build_entity_index_from_relations(
    kb_id: str,
    relations: list[KgRelation],
) -> EntityIndexSnapshot:
    """由三元组列表构建实体倒排与共现邻接。"""
    snap = EntityIndexSnapshot(kb_id=kb_id)
    for rel in relations:
        _add_entity_chunk(snap, rel.subject, rel.chunk_id, rel.document_id)
        _add_entity_chunk(snap, rel.object_entity, rel.chunk_id, rel.document_id)

    for entities in snap.chunk_to_entities.values():
        elist = sorted(entities)
        for i, a in enumerate(elist):
            snap.cooccurrence.setdefault(a, set())
            for b in elist[i + 1 :]:
                snap.cooccurrence[a].add(b)
                snap.cooccurrence.setdefault(b, set()).add(a)

    snap.entity_names = sorted(snap.entity_to_chunks.keys(), key=len, reverse=True)
    return snap


async def build_entity_index(db: AsyncSession, kb_id: str) -> EntityIndexSnapshot:
    """加载或构建知识库实体索引（LRU 缓存）。"""
    cached = _cache_get(kb_id)
    if cached is not None:
        return cached

    relations = await load_relations(db, kb_id)
    snap = build_entity_index_from_relations(kb_id, relations)
    _cache_set(snap)
    return snap


def extract_query_entities(query: str, entity_names: list[str]) -> list[str]:
    """查询侧实体抽取：linking + G-L1 分解回退。"""
    seeds = link_entities_in_query(query, entity_names)
    if not seeds:
        decomposed = get_multi_hop_anchors(query)
        if decomposed:
            seeds = link_entities_in_query(" ".join(decomposed), entity_names)
    return seeds


def _pagerank_entity_scores(
    snap: EntityIndexSnapshot,
    seeds: list[str],
    *,
    iterations: int = 12,
    damping: float = 0.85,
) -> dict[str, float]:
    """种子实体子图上的轻量 PageRank（用于二跳 chunk 加权）。"""
    nodes: set[str] = set(seeds)
    for s in seeds:
        nodes |= snap.cooccurrence.get(s, set())
    if not nodes:
        return {}

    nodes_list = sorted(nodes)
    n = len(nodes_list)
    idx = {name: i for i, name in enumerate(nodes_list)}
    scores = [1.0 / n] * n
    seed_set = set(seeds)
    teleport = [damping / len(seeds) if name in seed_set else 0.0 for name in nodes_list]
    if not any(teleport):
        teleport = [1.0 / n] * n

    out_weight: list[float] = []
    neighbors: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for name in nodes_list:
        adj = snap.cooccurrence.get(name, set()) & nodes
        out_weight.append(float(len(adj)) or 1.0)
        for other in adj:
            if other in idx:
                neighbors[idx[name]].append((idx[other], 1.0))

    for _ in range(iterations):
        new_scores = [(1.0 - damping) * teleport[i] for i in range(n)]
        for i in range(n):
            if not neighbors[i]:
                new_scores[i] += damping * scores[i]
                continue
            share = damping * scores[i] / out_weight[i]
            for j, w in neighbors[i]:
                new_scores[j] += share * w
        scores = new_scores

    return {nodes_list[i]: scores[i] for i in range(n)}


def rank_chunks_linear(
    snap: EntityIndexSnapshot,
    seeds: list[str],
    *,
    top_k: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """一跳 chunk + 共现二跳扩展 + PageRank 加权。"""
    if not seeds:
        return {}, []

    chunk_scores: dict[str, float] = defaultdict(float)
    paths: list[dict[str, Any]] = []

    for rank, entity in enumerate(seeds):
        hop_w = 1.0 / (1 + rank * 0.1)
        for cid in snap.entity_to_chunks.get(entity, ()):
            chunk_scores[cid] += hop_w
            paths.append(
                {
                    "mode": "linear",
                    "hop": 1,
                    "entity": entity,
                    "chunk_id": cid,
                }
            )

    pr = _pagerank_entity_scores(snap, seeds)
    for entity, pr_score in pr.items():
        if entity in seeds:
            continue
        for cid in snap.entity_to_chunks.get(entity, ()):
            chunk_scores[cid] += 0.5 * pr_score
            paths.append(
                {
                    "mode": "linear",
                    "hop": 2,
                    "entity": entity,
                    "chunk_id": cid,
                    "pr_score": round(pr_score, 6),
                }
            )

    if not chunk_scores:
        return {}, paths

    max_score = max(chunk_scores.values()) or 1.0
    normalized = {cid: round(score / max_score, 6) for cid, score in chunk_scores.items()}
    return normalized, paths[:30]


async def search_entity_index(
    db: AsyncSession,
    kb_id: str,
    query: str,
    *,
    top_k: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """LinearRAG 检索：实体倒排 + 共现扩展 + PageRank。"""
    if not getattr(settings, "GRAPH_ENABLED", True):
        return [], []

    k = top_k or getattr(settings, "RETRIEVAL_TOP_K", 5)
    snap = await build_entity_index(db, kb_id)
    if not snap.entity_names:
        return [], []

    seeds = extract_query_entities(query, snap.entity_names)
    if not seeds:
        return [], []

    effective_k = min(k * 2, 12) if len(seeds) >= 2 else k
    chunk_scores, paths = rank_chunks_linear(snap, seeds, top_k=effective_k)
    if not chunk_scores:
        return [], paths

    ranked_ids = sorted(chunk_scores.keys(), key=lambda x: chunk_scores[x], reverse=True)[
        : max(effective_k * 2, 10)
    ]
    chunks = (
        (
            await db.execute(
                select(Chunk).where(
                    Chunk.id.in_(ranked_ids),
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
    for cid in ranked_ids:
        chunk = chunk_map.get(cid)
        if not chunk:
            continue
        sources.append(
            {
                "chunk_id": cid,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "document_id": chunk.document_id,
                "score": chunk_scores[cid],
                "source": "graph-linear",
                "graph_seeds": seeds,
                "graph_mode": "linear",
            }
        )
    return sources[:effective_k], paths
