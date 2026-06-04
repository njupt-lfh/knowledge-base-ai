"""v2 评测集构建逻辑（Week 2）。

自然问法、多 relevant 标注、kg 多跳、近域负例。
"""

from __future__ import annotations

import random
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import Chunk
from ..models.conversation import Conversation, Message
from ..models.kg_relation import KgRelation
from ..models.knowledge_base import KnowledgeBase

BANNED_PHRASES = ("根据本知识库", "本知识库内容", "知识库中关于「本知识库")

FACT_TEMPLATES = (
    "{term}是什么？",
    "介绍一下{term}。",
    "{term}有哪些要点？",
    "文档里关于{term}说了什么？",
)

CONCEPT_TEMPLATES = (
    "请解释{term}的含义。",
    "{term}有什么特点？",
    "如何理解{term}？",
)

NEAR_DOMAIN_TEMPLATES = (
    "本库里有关于「{wrong_term}」的详细说明吗？",
    "{wrong_term}在本知识库中是如何描述的？",
    "请介绍知识库里{wrong_term}相关章节。",
)

UNRELATED_QUESTIONS = (
    "量子纠缠实验的具体操作步骤是什么？",
    "CRISPR 基因编辑的详细实验流程是怎样的？",
    "火星殖民基地的建设方案有哪些？",
    "深海热泉生态系统的完整分类学报告？",
)


def _first_sentence(text: str, max_len: int = 80) -> str:
    t = re.sub(r"\s+", " ", text.strip())
    for sep in ("。", "！", "？", ".", "\n"):
        if sep in t:
            t = t.split(sep)[0]
            break
    return t[:max_len]


def _extract_term(content: str) -> str:
    """从 chunk 正文提取问句用词项。"""
    latin = re.findall(r"(?a)[A-Za-z][\w.-]{1,20}", content)
    if latin:
        return latin[0][:24]
    cjk = re.findall(r"[\u4e00-\u9fff]{2,8}", content)
    for w in cjk:
        if w not in ("知识库", "文档", "内容", "相关", "要点", "介绍"):
            return w
    return _first_sentence(content, 12) or "该主题"


def _has_banned_phrase(text: str) -> bool:
    return any(p in text for p in BANNED_PHRASES)


def _supporting_chunk(chunks: list[Chunk], primary: Chunk) -> Chunk | None:
    """同文档相邻 chunk 作为 supporting。"""
    same_doc = sorted(
        [c for c in chunks if c.document_id == primary.document_id and c.id != primary.id],
        key=lambda x: x.chunk_index,
    )
    if not same_doc:
        return None
    for c in same_doc:
        if abs(c.chunk_index - primary.chunk_index) <= 2:
            return c
    return same_doc[0]


async def _load_user_questions(db: AsyncSession, kb_id: str, limit: int) -> list[str]:
    rows = (
        await db.execute(
            select(Message.content)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.role == "user",
                Conversation.knowledge_base_id == kb_id,
                func.length(Message.content) > 10,
            )
            .order_by(func.random())
            .limit(limit)
        )
    ).all()
    out: list[str] = []
    for (content,) in rows:
        q = (content or "").strip()
        if q and not _has_banned_phrase(q) and "?" not in q[:3]:
            if not q.endswith(("?", "？")):
                q = q.rstrip("。") + "？"
            out.append(q)
    return out


async def _kg_multi_hop_pairs(
    db: AsyncSession, kb_id: str, limit: int
) -> list[tuple[str, str, str, str, str]]:
    """返回 (chunk_a, chunk_b, subj, pred, obj) 列表。"""
    rels = (
        (
            await db.execute(
                select(KgRelation)
                .where(
                    KgRelation.knowledge_base_id == kb_id,
                    KgRelation.is_active.is_(True),
                )
                .order_by(func.random())
                .limit(300)
            )
        )
        .scalars()
        .all()
    )
    by_object: dict[str, list[KgRelation]] = {}
    for rel in rels:
        by_object.setdefault(rel.object_entity, []).append(rel)

    pairs: list[tuple[str, str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for r1 in rels:
        for r2 in by_object.get(r1.object_entity, []):
            if r1.chunk_id == r2.chunk_id:
                continue
            key = tuple(sorted((r1.chunk_id, r2.chunk_id)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append(
                (r1.chunk_id, r2.chunk_id, r1.subject, r1.predicate, r1.object_entity)
            )
            if len(pairs) >= limit:
                return pairs
    return pairs


def _make_sample(
    *,
    idx: int,
    kb_id: str,
    kb_name: str,
    q_type: str,
    question: str,
    ground_truth: str,
    chunk_ids: list[str],
    grades: dict[str, str] | None = None,
    negative_subtype: str | None = None,
) -> dict[str, Any]:
    sample: dict[str, Any] = {
        "id": f"{kb_id[:8]}-v2-{idx:03d}",
        "dataset_version": "v2",
        "kb_id": kb_id,
        "kb_name": kb_name,
        "q_type": q_type,
        "question": question,
        "ground_truth": ground_truth,
        "relevant_chunk_ids": chunk_ids,
    }
    if grades:
        sample["relevance_grades"] = grades
    if negative_subtype:
        sample["negative_subtype"] = negative_subtype
    return sample


def _fact_chunk_bundle(primary: Chunk, chunks: list[Chunk]) -> tuple[list[str], dict[str, str]]:
    sup = _supporting_chunk(chunks, primary)
    ids = [primary.id]
    grades: dict[str, str] = {primary.id: "primary"}
    if sup:
        ids.append(sup.id)
        grades[sup.id] = "supporting"
    return ids, grades


async def _load_chunks_by_ids(db: AsyncSession, kb_id: str, ids: list[str]) -> dict[str, Chunk]:
    if not ids:
        return {}
    rows = (
        (
            await db.execute(
                select(Chunk).where(
                    Chunk.id.in_(ids),
                    Chunk.knowledge_base_id == kb_id,
                    Chunk.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return {c.id: c for c in rows}


async def build_v2_samples_for_kb(
    db: AsyncSession,
    kb_id: str,
    kb_name: str,
    chunks: list[Chunk],
    *,
    start_idx: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], int]:
    """为单库生成 40 条 v2 样本。"""
    active = [c for c in chunks if c.is_active and len(c.content.strip()) > 40]
    if len(active) < 30:
        return [], start_idx

    samples: list[dict[str, Any]] = []
    idx = start_idx
    used_questions: set[str] = set()

    def add(**kwargs: Any) -> bool:
        nonlocal idx
        q = kwargs["question"]
        if _has_banned_phrase(q) or q in used_questions:
            return False
        used_questions.add(q)
        idx += 1
        samples.append(_make_sample(idx=idx, kb_id=kb_id, kb_name=kb_name, **kwargs))
        return True

    # 16 fact
    conv_qs = await _load_user_questions(db, kb_id, limit=8)
    conv_i = 0
    fact_i = 0
    for ci, c in enumerate(active):
        if fact_i >= 16:
            break
        ids, grades = _fact_chunk_bundle(c, active)
        if conv_i < len(conv_qs) and conv_i < 4:
            question = conv_qs[conv_i]
            conv_i += 1
        else:
            term = _extract_term(c.content)
            question = FACT_TEMPLATES[fact_i % len(FACT_TEMPLATES)].format(term=term)
        if add(
            q_type="fact",
            question=question,
            ground_truth=c.content[:500].strip(),
            chunk_ids=ids,
            grades=grades,
        ):
            fact_i += 1
            continue
        fallback = f"{_extract_term(c.content)}相关要点（{ci + 1}）？"
        if add(
            q_type="fact",
            question=fallback,
            ground_truth=c.content[:500].strip(),
            chunk_ids=ids,
            grades=grades,
        ):
            fact_i += 1

    # 6 concept
    concept_i = 0
    for ci, c in enumerate(active[16:], start=16):
        if concept_i >= 6:
            break
        term = _extract_term(c.content)
        question = CONCEPT_TEMPLATES[concept_i % len(CONCEPT_TEMPLATES)].format(term=term)
        if add(
            q_type="concept",
            question=question,
            ground_truth=c.content[:600].strip(),
            chunk_ids=[c.id],
            grades={c.id: "primary"},
        ):
            concept_i += 1

    # 10 multi_hop
    kg_pairs = await _kg_multi_hop_pairs(db, kb_id, limit=12)
    extra_ids = [p[0] for p in kg_pairs] + [p[1] for p in kg_pairs]
    chunk_map = {c.id: c for c in active}
    chunk_map.update(await _load_chunks_by_ids(db, kb_id, list(set(extra_ids))))

    mh_done = 0
    for ca, cb, subj, pred, obj in kg_pairs:
        if mh_done >= 10:
            break
        a, b = chunk_map.get(ca), chunk_map.get(cb)
        if not a or not b:
            continue
        question = f"「{subj}」和「{obj}」之间有什么联系？（通过{pred}）"
        if add(
            q_type="multi_hop",
            question=question,
            ground_truth=f"{_first_sentence(a.content)}\n{_first_sentence(b.content)}",
            chunk_ids=[ca, cb],
            grades={ca: "primary", cb: "primary"},
        ):
            mh_done += 1

    for i in range(0, len(active) - 1, 2):
        if mh_done >= 10:
            break
        a, b = active[i], active[i + 1]
        question = (
            f"综合两段内容，「{_first_sentence(a.content, 30)}」"
            f"与「{_first_sentence(b.content, 30)}」有何关联？"
        )
        if add(
            q_type="multi_hop",
            question=question,
            ground_truth=f"{_first_sentence(a.content)}\n{_first_sentence(b.content)}",
            chunk_ids=[a.id, b.id],
            grades={a.id: "primary", b.id: "supporting"},
        ):
            mh_done += 1

    # 8 negative（4 unrelated + 4 near_domain）
    wrong_terms = ["React 18 Suspense 源码", "量子纠缠", "CRISPR", "火星基地"]
    neg_u = 0
    for i in range(20):
        if neg_u >= 4:
            break
        q = UNRELATED_QUESTIONS[(idx + i) % len(UNRELATED_QUESTIONS)]
        if add(
            q_type="negative",
            question=q,
            ground_truth="知识库中暂无相关信息。",
            chunk_ids=[],
            negative_subtype="unrelated",
        ):
            neg_u += 1

    neg_n = 0
    for i in range(20):
        if neg_n >= 4:
            break
        wrong = wrong_terms[(idx + i) % len(wrong_terms)]
        question = NEAR_DOMAIN_TEMPLATES[i % len(NEAR_DOMAIN_TEMPLATES)].format(
            wrong_term=wrong
        )
        if add(
            q_type="negative",
            question=question,
            ground_truth="知识库中暂无相关信息。",
            chunk_ids=[],
            negative_subtype="near_domain",
        ):
            neg_n += 1

    return samples[:40], idx


async def build_v2_dataset(
    db: AsyncSession,
    *,
    target_kbs: int = 5,
    samples_per_kb: int = 40,
    seed: int = 42,
    kb_ids: list[str] | None = None,
) -> dict[str, Any]:
    """构建完整 v2 数据集 dict。"""
    rng = random.Random(seed)

    if kb_ids:
        kb_rows = (
            await db.execute(
                select(KnowledgeBase.id, KnowledgeBase.name, func.count(Chunk.id))
                .join(Chunk, Chunk.knowledge_base_id == KnowledgeBase.id)
                .where(KnowledgeBase.id.in_(kb_ids))
                .group_by(KnowledgeBase.id)
                .having(func.count(Chunk.id) >= 30)
            )
        ).all()
        kb_rows = sorted(kb_rows, key=lambda r: kb_ids.index(r[0]))
    else:
        kb_rows = (
            await db.execute(
                select(KnowledgeBase.id, KnowledgeBase.name, func.count(Chunk.id))
                .join(Chunk, Chunk.knowledge_base_id == KnowledgeBase.id)
                .group_by(KnowledgeBase.id)
                .having(func.count(Chunk.id) >= 30)
                .order_by(func.count(Chunk.id).desc())
                .limit(target_kbs)
            )
        ).all()

    all_samples: list[dict] = []
    kb_meta: list[dict] = []
    idx = 0

    for kb_id, kb_name, _ in kb_rows:
        chunks = (
            (
                await db.execute(
                    select(Chunk)
                    .where(Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True))
                    .order_by(Chunk.hit_count.desc(), Chunk.chunk_index)
                    .limit(80)
                )
            )
            .scalars()
            .all()
        )
        batch, idx = await build_v2_samples_for_kb(
            db, kb_id, kb_name or kb_id, list(chunks), start_idx=idx, rng=rng
        )
        if len(batch) < samples_per_kb:
            raise ValueError(f"kb {kb_id}: only {len(batch)} v2 samples")
        all_samples.extend(batch[:samples_per_kb])
        kb_meta.append(
            {"kb_id": kb_id, "kb_name": kb_name, "sample_count": samples_per_kb}
        )

    return {
        "version": "2.0",
        "dataset_version": "v2",
        "description": "Week 2 自然问法评测集 — 每库 40 条，含多 relevant 与近域负例",
        "primary_kb_id": kb_meta[0]["kb_id"],
        "knowledge_bases": kb_meta,
        "samples": all_samples,
    }
