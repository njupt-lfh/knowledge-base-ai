"""历史 chunk 图谱回填

验证内容：
  - 为 kg_relations 批量抽取三元组

运行方式（在 backend 目录）:
  python scripts/backfill_graph.py --mock

预期结果：打印 PASS 并退出码 0；失败时退出码 1（部分脚本 SKIP 为 0）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# --mock 须在 import app 之前设置，否则 settings 已缓存 LLM_MOCK_MODE
if "--mock" in sys.argv:
    os.environ["LLM_MOCK_MODE"] = "true"

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

EVAL_DATA = ROOT / "data" / "eval_qa_dataset.json"


def _preflight() -> tuple[bool, str]:
    """回填前检查 LLM/API 配置是否满足要求。"""
    from app.core.config import settings

    if settings.LLM_MOCK_MODE and "--mock" not in sys.argv:
        return False, "LLM_MOCK_MODE=true，全库 LLM backfill 需设为 false"
    if not settings.VOLCENGINE_API_KEY:
        return False, "VOLCENGINE_API_KEY 未配置"
    graph_model = (settings.GRAPH_EXTRACTION_MODEL or "").strip()
    if not graph_model and "--mock" not in sys.argv:
        return False, "GRAPH_EXTRACTION_MODEL 未配置（应填 ep-xxx 接入点 ID）"
    return True, graph_model or "mock-rules"


async def _run(args: argparse.Namespace) -> int:
    """执行主逻辑并返回进程退出码。"""
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.kg_relation import KgRelation
    from app.services.graph_store_service import invalidate_graph_cache, sync_chunk_graph
    from sqlalchemy import func, select

    ok, model_info = _preflight()
    if not ok:
        print(f"FAIL: {model_info}")
        return 1

    await init_db()

    kb_filter: set[str] | None = None
    if args.eval_kbs_only and EVAL_DATA.exists():
        data = json.loads(EVAL_DATA.read_text(encoding="utf-8"))
        kb_filter = {s["kb_id"] for s in data.get("samples", [])}
        print(f"eval KB filter: {len(kb_filter)} knowledge bases")

    async with async_session() as db:
        total_active = (
            await db.execute(
                select(func.count()).select_from(Chunk).where(Chunk.is_active.is_(True))
            )
        ).scalar() or 0
        rel_before = (await db.execute(select(func.count()).select_from(KgRelation))).scalar() or 0

        q = (
            select(Chunk)
            .where(Chunk.is_active.is_(True))
            .order_by(Chunk.knowledge_base_id, Chunk.chunk_index)
        )
        if kb_filter:
            q = q.where(Chunk.knowledge_base_id.in_(kb_filter))
        if args.kb_id:
            q = q.where(Chunk.knowledge_base_id == args.kb_id)

        chunks = (await db.execute(q)).scalars().all()
        if args.limit > 0:
            chunks = chunks[: args.limit]

        if args.skip_existing:
            existing = set(
                (await db.execute(select(KgRelation.chunk_id).distinct())).scalars().all()
            )
            skipped = len(chunks)
            chunks = [c for c in chunks if c.id not in existing]
            print(f"WARN: --skip-existing 跳过 {skipped - len(chunks)} 条；LLM 全量请勿加此参数")

        total = len(chunks)
        if total == 0:
            print("PASS: nothing to backfill")
            return 0

        est_tokens = total * 900
        print("=== LLM Graph Backfill Preflight ===")
        print(f"  extraction_model: {model_info}")
        print(f"  active_chunks(total): {total_active}")
        print(f"  to_process: {total}")
        print(f"  relations_before: {rel_before}")
        print(f"  est_tokens(~): {est_tokens:,}  (GRAPH_EXTRACTION_MODEL 额度)")
        if args.skip_existing:
            print("  mode: incremental (skip existing)")
        else:
            print("  mode: FULL re-extract (replaces mock/rule triples per chunk)")

        t0 = time.perf_counter()
        synced = 0
        triples = 0
        errors = 0
        touched_kbs: set[str] = set()

        for i, c in enumerate(chunks, start=1):
            try:
                n = await sync_chunk_graph(
                    db, c.knowledge_base_id, c.id, c.document_id, c.content, commit=False
                )
                triples += n
                synced += 1
                touched_kbs.add(c.knowledge_base_id)
            except Exception as e:
                errors += 1
                print(f"  ERROR chunk {c.id[:8]}: {e}")
            if args.delay_ms > 0:
                await asyncio.sleep(args.delay_ms / 1000.0)
            if i % 50 == 0:
                await db.commit()
                for kb in touched_kbs:
                    invalidate_graph_cache(kb)
            if i % 20 == 0 or i == total:
                elapsed = round(time.perf_counter() - t0, 1)
                rate = round(i / elapsed, 2) if elapsed > 0 else 0
                print(f"  {i}/{total} chunks, +{triples} triples, err={errors}, {rate}/s")

        await db.commit()
        for kb in touched_kbs:
            invalidate_graph_cache(kb)

        rel_after = (await db.execute(select(func.count()).select_from(KgRelation))).scalar() or 0
        covered = (
            await db.execute(select(func.count(func.distinct(KgRelation.chunk_id))))
        ).scalar() or 0
        elapsed = round(time.perf_counter() - t0, 1)
        print(
            f"PASS: backfill done — {synced} chunks, +{triples} triples this run, "
            f"relations {rel_before}->{rel_after}, chunks_covered={covered}/{total_active}, "
            f"errors={errors}, {elapsed}s"
        )
        return 1 if errors > synced * 0.1 else 0


def main() -> int:
    """脚本 CLI 入口。"""
    parser = argparse.ArgumentParser(description="Backfill kg_relations for existing chunks")
    parser.add_argument("--kb-id", default="", help="single KB id")
    parser.add_argument("--eval-kbs-only", action="store_true", help="only eval dataset KBs")
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="skip chunks already in kg_relations（LLM 全量回填不要用）",
    )
    parser.add_argument("--mock", action="store_true", help="rule-based extraction only (zero LLM)")
    parser.add_argument("--delay-ms", type=int, default=0, help="delay between chunks (rate limit)")
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
