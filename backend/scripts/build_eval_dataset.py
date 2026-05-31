"""从 SQLite 为多个知识库生成评测 QA（每库 20 条）并合并写入 eval_qa_dataset.json"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.core.database import async_session  # noqa: E402
from app.models.chunk import Chunk  # noqa: E402
from app.models.knowledge_base import KnowledgeBase  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

OUTPUT = ROOT / "data" / "eval_qa_dataset.json"
TARGET_KBS = 5
SAMPLES_PER_KB = 20


def _first_sentence(text: str, max_len: int = 120) -> str:
    t = re.sub(r"\s+", " ", text.strip())
    for sep in ("。", "！", "？", ".", "\n"):
        if sep in t:
            t = t.split(sep)[0] + sep
            break
    return t[:max_len]


def _make_samples(kb_id: str, kb_name: str, chunks: list[Chunk]) -> list[dict]:
    active = [c for c in chunks if c.is_active and len(c.content.strip()) > 40]
    if len(active) < 20:
        return []

    samples: list[dict] = []
    idx = 0

    def add(q_type: str, question: str, ground_truth: str, chunk_ids: list[str]) -> None:
        nonlocal idx
        idx += 1
        samples.append(
            {
                "id": f"{kb_id[:8]}-qa-{idx:03d}",
                "kb_id": kb_id,
                "kb_name": kb_name,
                "q_type": q_type,
                "question": question,
                "ground_truth": ground_truth,
                "relevant_chunk_ids": chunk_ids,
            }
        )

    # 10 fact + 4 concept + 4 multi_hop + 2 negative = 20
    for c in active[:10]:
        snippet = _first_sentence(c.content)
        add(
            "fact",
            f"根据本知识库内容，{snippet[:30]}… 相关要点是什么？",
            c.content[:400].strip(),
            [c.id],
        )

    for c in active[10:14]:
        sn = _first_sentence(c.content)
        add(
            "concept",
            f"请解释知识库中与「{sn[:20]}」相关的概念。",
            c.content[:500].strip(),
            [c.id],
        )

    pair_start = 14
    for i in range(2):
        a, b = active[pair_start + i * 2], active[pair_start + i * 2 + 1]
        add(
            "multi_hop",
            f"综合知识库中两段内容，说明「{_first_sentence(a.content, 40)}」与「{_first_sentence(b.content, 40)}」有何关联？",
            f"{_first_sentence(a.content)}\n{_first_sentence(b.content)}",
            [a.id, b.id],
        )

    # 2 negative
    add(
        "negative",
        "本知识库中关于「量子纠缠实验步骤」的详细记录是什么？",
        "知识库中暂无相关信息。",
        [],
    )
    add(
        "negative",
        "请介绍本知识库中 React 18 Suspense 源码分析章节。",
        "知识库中暂无相关信息。",
        [],
    )

    return samples[:SAMPLES_PER_KB]


async def main() -> int:
    all_samples: list[dict] = []
    kb_meta: list[dict] = []

    async with async_session() as db:
        kb_rows = (
            await db.execute(
                select(KnowledgeBase.id, KnowledgeBase.name, func.count(Chunk.id))
                .join(Chunk, Chunk.knowledge_base_id == KnowledgeBase.id)
                .group_by(KnowledgeBase.id)
                .having(func.count(Chunk.id) >= 20)
                .order_by(func.count(Chunk.id).desc())
                .limit(TARGET_KBS)
            )
        ).all()

        for kb_id, kb_name, _ in kb_rows:
            chunks = (
                (
                    await db.execute(
                        select(Chunk)
                        .where(Chunk.knowledge_base_id == kb_id, Chunk.is_active.is_(True))
                        .order_by(Chunk.hit_count.desc(), Chunk.chunk_index)
                        .limit(30)
                    )
                )
                .scalars()
                .all()
            )
            batch = _make_samples(kb_id, kb_name or kb_id, list(chunks))
            if len(batch) < SAMPLES_PER_KB:
                print(f"WARN: {kb_id} only {len(batch)} samples")
            all_samples.extend(batch)
            kb_meta.append({"kb_id": kb_id, "kb_name": kb_name, "sample_count": len(batch)})

    if len(all_samples) < TARGET_KBS * SAMPLES_PER_KB:
        print(f"FAIL: expected>={TARGET_KBS * SAMPLES_PER_KB}, got {len(all_samples)}")
        return 1

    data = {
        "version": "2.0",
        "description": "Phase 0 多库评测集 — 每库 20 条 QA",
        "primary_kb_id": kb_meta[0]["kb_id"],
        "knowledge_bases": kb_meta,
        "samples": all_samples,
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: wrote {len(all_samples)} samples across {len(kb_meta)} KBs -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
