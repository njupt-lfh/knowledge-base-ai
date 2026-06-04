"""校验评测数据集

验证内容：
  - 格式、多库规模与 chunk 引用

运行方式（在 backend 目录）:
  python scripts/validate_eval_dataset.py

预期结果：打印 PASS 并退出码 0；失败时退出码 1（部分脚本 SKIP 为 0）。
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATA_FILE_V1 = ROOT / "data" / "eval_qa_dataset.json"
DATA_FILE_V2 = ROOT / "data" / "eval_qa_dataset_v2.json"
sys.path.insert(0, str(BACKEND))

REQUIRED_Q_TYPES = {"fact", "multi_hop", "concept", "negative"}
REQUIRED_SAMPLE_FIELDS = {"id", "kb_id", "q_type", "question", "ground_truth", "relevant_chunk_ids"}
MIN_KBS = 5
SAMPLES_PER_KB_V1 = 20
SAMPLES_PER_KB_V2 = 40


def _check_schema(samples: list[dict], *, version: str) -> list[str]:
    """校验样本 JSON 字段与 q_type 分布。"""
    errors: list[str] = []
    type_counts: Counter[str] = Counter()
    min_neg = MIN_KBS * 2 if version == "v1" else 40
    for s in samples:
        missing = REQUIRED_SAMPLE_FIELDS - set(s.keys())
        if missing:
            errors.append(f"{s.get('id')}: missing fields {missing}")
        qt = s.get("q_type")
        type_counts[qt] += 1
        if qt not in REQUIRED_Q_TYPES:
            errors.append(f"{s.get('id')}: invalid q_type {qt}")
        if version == "v2" and qt == "negative" and not s.get("negative_subtype"):
            errors.append(f"{s.get('id')}: negative missing negative_subtype")
    if type_counts.get("negative", 0) < min_neg:
        errors.append(f"need >= {min_neg} negative samples total")
    return errors


async def _check_chunks(samples: list[dict]) -> list[str]:
    """校验 relevant_chunk_ids 在 DB 中存在。"""
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
    """脚本 CLI 入口。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-db", action="store_true", help="skip chunk ID DB validation")
    parser.add_argument("--dataset", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()

    data_file = DATA_FILE_V2 if args.dataset == "v2" else DATA_FILE_V1
    per_kb = SAMPLES_PER_KB_V2 if args.dataset == "v2" else SAMPLES_PER_KB_V1

    if not data_file.exists():
        print(f"FAIL: missing {data_file}")
        return 1

    data = json.loads(data_file.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    kb_counts = Counter(s["kb_id"] for s in samples)

    errors = _check_schema(samples, version=args.dataset)
    if len(kb_counts) < MIN_KBS:
        errors.append(f"need >= {MIN_KBS} knowledge bases, got {len(kb_counts)}")
    for kb_id, cnt in kb_counts.items():
        if cnt < per_kb:
            errors.append(f"kb {kb_id}: need {per_kb} samples, got {cnt}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1

    if not args.skip_db:
        chunk_errors = asyncio.run(_check_chunks(samples))
        if chunk_errors:
            for e in chunk_errors:
                print(f"FAIL: {e}")
            return 1

    mode = "schema-only" if args.skip_db else "schema+chunks"
    print(f"PASS ({mode}): {data_file.name}")
    print(f"  samples: {len(samples)}")
    print(f"  knowledge_bases: {len(kb_counts)}")
    print(f"  per_kb: {dict(kb_counts)}")
    print(f"  primary_kb_id: {data.get('primary_kb_id')}")
    print(f"  dataset_version: {data.get('dataset_version', args.dataset)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
