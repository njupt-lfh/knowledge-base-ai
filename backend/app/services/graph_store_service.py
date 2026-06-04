"""轻量知识图谱存储（SQLite 三元组 + NetworkX 内存图）。

职责：
    入库时从 chunk 抽取三元组写入 KgRelation，检索时构建 NetworkX 有向图，
    支持实体 linking 与 BFS 多跳路径扩展。

在流水线中的位置：
    入库：document_service / chunk_service → sync_chunk_graph
    检索：GraphRetriever → build_networkx_graph / expand_graph_paths

依赖服务：
    - entity_extraction_service：chunk 级三元组抽取
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.chunk import Chunk
from ..models.kg_relation import KgRelation
from .entity_extraction_service import extract_triples_from_chunk

logger = logging.getLogger(__name__)

# LRU 图缓存：避免每次检索全量 load relations
_graph_cache: OrderedDict[str, nx.DiGraph] = OrderedDict()
_CACHE_MAX = 8


def _cache_get(kb_id: str) -> nx.DiGraph | None:
    """从 LRU 缓存获取 NetworkX 图。

    参数:
        kb_id: 知识库 ID

    返回:
        缓存的 DiGraph 或 None
    """
    g = _graph_cache.get(kb_id)
    if g is not None:
        _graph_cache.move_to_end(kb_id)
    return g


def _cache_set(kb_id: str, graph: nx.DiGraph) -> None:
    """写入 LRU 图缓存。

    参数:
        kb_id: 知识库 ID
        graph: NetworkX 有向图
    """
    _graph_cache[kb_id] = graph
    _graph_cache.move_to_end(kb_id)
    while len(_graph_cache) > _CACHE_MAX:
        _graph_cache.popitem(last=False)


def invalidate_graph_cache(kb_id: str) -> None:
    """使指定知识库的图缓存失效（三元组变更后调用）。

    参数:
        kb_id: 知识库 ID
    """
    _graph_cache.pop(kb_id, None)
    try:
        from .entity_index_service import invalidate_entity_index_cache

        invalidate_entity_index_cache(kb_id)
    except ImportError:
        pass


async def delete_relations_for_chunk(
    db: AsyncSession, chunk_id: str, *, commit: bool = True
) -> None:
    """删除 chunk 关联的全部三元组。

    参数:
        db: 数据库会话
        chunk_id: chunk ID
        commit: 是否立即提交
    """
    await db.execute(delete(KgRelation).where(KgRelation.chunk_id == chunk_id))
    if commit:
        await db.commit()


async def sync_chunk_graph(
    db: AsyncSession,
    kb_id: str,
    chunk_id: str,
    document_id: str,
    content: str,
    *,
    active: bool = True,
    commit: bool = True,
) -> int:
    """抽取并写入 chunk 关联三元组。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID
        chunk_id: chunk ID
        document_id: 文档 ID
        content: chunk 正文
        active: 是否活跃（非活跃则只删不写）
        commit: 是否提交

    返回:
        写入的三元组条数
    """
    if not getattr(settings, "GRAPH_ENABLED", True):
        return 0

    await delete_relations_for_chunk(db, chunk_id, commit=False)
    if not active or not content.strip():
        invalidate_graph_cache(kb_id)
        if commit:
            await db.commit()
        return 0

    triples = await extract_triples_from_chunk(content)
    if not triples:
        invalidate_graph_cache(kb_id)
        if commit:
            await db.commit()
        return 0

    for t in triples:
        db.add(
            KgRelation(
                knowledge_base_id=kb_id,
                chunk_id=chunk_id,
                document_id=document_id,
                subject=t["subject"],
                predicate=t["predicate"],
                object_entity=t["object"],
                confidence=float(t.get("confidence", 1.0)),
                is_active=True,
            )
        )
    if commit:
        await db.commit()
    invalidate_graph_cache(kb_id)
    return len(triples)


async def sync_chunks_graph(
    db: AsyncSession,
    kb_id: str,
    chunk_records: list[Chunk],
) -> int:
    """批量同步多个 chunk 的图谱三元组。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID
        chunk_records: chunk 记录列表

    返回:
        累计写入三元组条数
    """
    total = 0
    for c in chunk_records:
        total += await sync_chunk_graph(
            db,
            kb_id,
            c.id,
            c.document_id,
            c.content,
            active=bool(c.is_active if c.is_active is not None else True),
        )
    return total


async def load_relations(db: AsyncSession, kb_id: str) -> list[KgRelation]:
    """加载知识库下所有活跃三元组（chunk 亦须活跃）。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID

    返回:
        KgRelation 列表
    """
    result = await db.execute(
        select(KgRelation)
        .join(Chunk, Chunk.id == KgRelation.chunk_id)
        .where(
            KgRelation.knowledge_base_id == kb_id,
            KgRelation.is_active.is_(True),
            Chunk.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def build_networkx_graph(db: AsyncSession, kb_id: str) -> nx.DiGraph:
    """构建知识库的 NetworkX 有向图（优先从 LRU 缓存获取）。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID

    返回:
        有向图（节点=实体名，边属性含 chunk_id/predicate）
    """
    cached = _cache_get(kb_id)
    if cached is not None:
        return cached

    graph = nx.DiGraph()
    relations = await load_relations(db, kb_id)
    for r in relations:
        graph.add_edge(
            r.subject,
            r.object_entity,
            predicate=r.predicate,
            chunk_id=r.chunk_id,
            document_id=r.document_id,
        )
    _cache_set(kb_id, graph)
    return graph


async def list_entity_names(db: AsyncSession, kb_id: str) -> list[str]:
    """获取知识库中所有图谱实体名（长名优先，用于 entity linking）。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID

    返回:
        按长度降序排列的实体名列表
    """
    relations = await load_relations(db, kb_id)
    if not relations:
        return []
    names: set[str] = set()
    for rel in relations:
        names.add(rel.subject)
        names.add(rel.object_entity)
    return sorted(names, key=len, reverse=True)


def _edit_distance_le(s1: str, s2: str, max_dist: int = 1) -> bool:
    """判断两个字符串编辑距离是否 ≤ max_dist（仅用于短实体容错，Phase 3 G-L3）。"""
    if abs(len(s1) - len(s2)) > max_dist:
        return False
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    n, m = len(s1), len(s2)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        lo, hi = max(1, i - max_dist), min(m, i + max_dist)
        for j in range(lo, hi + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        if min(curr) > max_dist:
            return False
        prev = curr
    return prev[m] <= max_dist


def link_entities_in_query(
    query: str, entity_names: list[str], *, min_len: int = 2
) -> list[str]:
    """从 query 中链接图谱实体（子串/词项 + 编辑距离容错，Phase 3 G-L3）。

    参数:
        query: 用户查询
        entity_names: 图谱实体名列表（建议长名优先）
        min_len: 实体名最小长度

    返回:
        匹配到的实体名列表
    """
    import re

    q = query.strip()
    # CJK multi-gram: 2~4 字窗口（提升短实体召回）
    cjk_terms: set[str] = set()
    cjk_segs = re.findall(r"[一-鿿]+", q)
    for seg in cjk_segs:
        for win in (4, 3, 2):
            for i in range(len(seg) - win + 1):
                cjk_terms.add(seg[i : i + win])
    latin_terms = set(re.findall(r"[a-zA-Z0-9_]{2,}", q))
    terms = cjk_terms | latin_terms
    stop = {
        "综合", "知识库", "内容", "说明", "有何", "关联", "两段", "之间",
        "关系", "有什么区别", "有什么", "是什么", "如何", "怎么", "哪些",
    }
    terms -= stop

    hits: list[str] = []
    seen: set[str] = set()
    for name in entity_names:
        if len(name) < min_len or name in seen:
            continue
        # 1) 精确子串匹配
        matched = name in q
        # 2) multi-gram 重叠
        if not matched:
            for t in terms:
                if len(t) >= 2 and (t in name or name in t):
                    matched = True
                    break
        # 3) 编辑距离 ≤1（仅短实体 2-4 字，避免假阳性）
        if not matched and 2 <= len(name) <= 4:
            for t in terms:
                if abs(len(t) - len(name)) <= 1 and _edit_distance_le(t, name):
                    matched = True
                    break
        if matched:
            hits.append(name)
            seen.add(name)
    return hits


def expand_graph_paths(
    graph: nx.DiGraph,
    seed_entities: list[str],
    *,
    max_hops: int = 2,
    anchor_hard_filter: bool = True,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    """BFS 多跳扩展，聚合 chunk 分数与路径列表（Phase 3 G-L2：anchor 约束）。

    参数:
        graph: NetworkX 有向图
        seed_entities: 种子实体列表
        max_hops: 最大跳数

    返回:
        (chunk_id → 分数, 路径 dict 列表)
    """
    chunk_scores: dict[str, float] = {}
    paths: list[dict[str, Any]] = []
    if not seed_entities or graph.number_of_edges() == 0:
        return chunk_scores, paths

    seed_set = set(seed_entities)
    for seed in seed_entities:
        if seed not in graph:
            continue
        frontier: list[tuple[str, int, list[str]]] = [(seed, 0, [seed])]
        visited: set[str] = {seed}
        while frontier:
            node, depth, path_nodes = frontier.pop(0)
            edges = list(graph.out_edges(node, data=True))
            edges += [(v, u, d) for u, v, d in graph.in_edges(node, data=True)]
            for u, v, data in edges:
                neighbor = v if u == node else u
                cid = data.get("chunk_id")
                pred = data.get("predicate", "关联")
                hop = depth + 1
                if cid:
                    new_path = path_nodes + [neighbor]
                    # Phase 3 G-L2: anchor 约束 — 路径至少覆盖 2 个 seed 实体
                    anchor_hits = len(set(new_path) & seed_set)
                    score = 1.0 / hop
                    if anchor_hits >= 2:
                        score *= 1.2  # 多锚点路径加分
                    chunk_scores[cid] = max(chunk_scores.get(cid, 0.0), score)
                    paths.append(
                        {
                            "subject": node,
                            "predicate": pred,
                            "object": neighbor,
                            "chunk_id": cid,
                            "hops": hop,
                            "anchor_hits": anchor_hits,
                        }
                    )
                if neighbor not in visited and hop < max_hops:
                    visited.add(neighbor)
                    frontier.append((neighbor, hop, path_nodes + [neighbor]))

    # Phase 3 G-L2: 多种子时硬过滤 — 仅保留覆盖 ≥2 个 anchor 的路径（legacy 可关闭）
    if anchor_hard_filter and len(seed_entities) >= 2:
        filtered_scores: dict[str, float] = {}
        filtered_paths: list[dict[str, Any]] = []
        for cid, score in chunk_scores.items():
            # 取该 chunk 关联路径中 anchor_hits 的最大值
            cid_paths = [p for p in paths if p.get("chunk_id") == cid]
            max_hits = max((p.get("anchor_hits", 1) for p in cid_paths), default=1)
            if max_hits >= 2:
                filtered_scores[cid] = score
        for p in paths:
            if p.get("chunk_id") in filtered_scores:
                filtered_paths.append(p)
        return filtered_scores, filtered_paths[:20]

    return chunk_scores, paths[:20]


async def graph_snapshot(
    db: AsyncSession,
    kb_id: str,
    *,
    limit_nodes: int = 200,
) -> dict[str, Any]:
    """获取知识图谱快照（供前端可视化）。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID
        limit_nodes: 最多展示的实体节点数（按出现频次截断）

    返回:
        含 nodes、edges、relation_count、node_count 的 dict
    """
    relations = await load_relations(db, kb_id)
    nodes: dict[str, int] = {}
    edges: list[dict] = []
    for r in relations:
        nodes[r.subject] = nodes.get(r.subject, 0) + 1
        nodes[r.object_entity] = nodes.get(r.object_entity, 0) + 1
        edges.append(
            {
                "source": r.subject,
                "target": r.object_entity,
                "predicate": r.predicate,
                "chunk_id": r.chunk_id,
            }
        )

    if not edges:
        return {
            "nodes": [],
            "edges": [],
            "relation_count": 0,
            "node_count": 0,
        }

    cap = max(limit_nodes, 1)
    ranked = sorted(nodes.items(), key=lambda x: x[1], reverse=True)
    keep = {name for name, _ in ranked[:cap]}
    if len(keep) < len(nodes):
        edges = [
            e
            for e in edges
            if e["source"] in keep and e["target"] in keep
        ]
        nodes = {n: nodes[n] for n in keep if n in nodes}

    node_list = [
        {"id": name, "name": name, "weight": weight}
        for name, weight in sorted(nodes.items(), key=lambda x: x[1], reverse=True)
    ]
    return {
        "nodes": node_list,
        "edges": edges,
        "relation_count": len(edges),
        "node_count": len(node_list),
    }
