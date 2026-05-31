"""校验 eval_qa_dataset.json 格式、多库规模与 chunk 引用"""

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATA_FILE = ROOT / "data" / "eval_qa_dataset.json"
sys.path.insert(0, str(BACKEND))

REQUIRED_Q_TYPES = {"fact", "multi_hop", "concept", "negative"}
REQUIRED_SAMPLE_FIELDS = {"id", "kb_id", "q_type", "question", "ground_truth", "relevant_chunk_ids"}
MIN_KBS = 5
SAMPLES_PER_KB = 20


def _check_schema(samples: list[dict]) -> list[str]:
    errors: list[str] = []
    type_counts: Counter[str] = Counter()
    for s in samples:
        missing = REQUIRED_SAMPLE_FIELDS - set(s.keys())
        if missing:
            errors.append(f"{s.get('id')}: missing fields {missing}")
        qt = s.get("q_type")
        type_counts[qt] += 1
        if qt not in REQUIRED_Q_TYPES:
            errors.append(f"{s.get('id')}: invalid q_type {qt}")
    if type_counts.get("negative", 0) < MIN_KBS * 2:
        errors.append(f"need >= {MIN_KBS * 2} negative samples total")
    return errors


async def _check_chunks(samples: list[dict]) -> list[str]:
    from app.core.database import async_session
    from app.models.chunk import Chunk
    from sqlalchemy import select

    ids = set()
    for s in samples:
        ids.update(x for x in (s.get("relevant_chunk_ids") or []) if x)
    if not ids:
        return []

    async with async_session() as db:
        found: set[str] = set()
        id_list = list(ids)
        for i in range(0, len(id_list), 50):
            batch = id_list[i : i + 50]
            rows = (await db.execute(select(Chunk.id).where(Chunk.id.in_(batch)))).all()
            found.update(r[0] for r in rows)
    missing = ids - found
    if missing:
        return [f"chunk ids not in DB: {list(missing)[:5]}..."]
    return []


def main() -> int:
    if not DATA_FILE.exists():
        print(f"FAIL: missing {DATA_FILE}")
        return 1

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    kb_counts = Counter(s["kb_id"] for s in samples)

    errors = _check_schema(samples)
    if len(kb_counts) < MIN_KBS:
        errors.append(f"need >= {MIN_KBS} knowledge bases, got {len(kb_counts)}")
    for kb_id, cnt in kb_counts.items():
        if cnt < SAMPLES_PER_KB:
            errors.append(f"kb {kb_id}: need {SAMPLES_PER_KB} samples, got {cnt}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1

    chunk_errors = asyncio.run(_check_chunks(samples))
    if chunk_errors:
        for e in chunk_errors:
            print(f"FAIL: {e}")
        return 1

    print("PASS: eval_qa_dataset.json")
    print(f"  samples: {len(samples)}")
    print(f"  knowledge_bases: {len(kb_counts)}")
    print(f"  per_kb: {dict(kb_counts)}")
    print(f"  primary_kb_id: {data.get('primary_kb_id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
