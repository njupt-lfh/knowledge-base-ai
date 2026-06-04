"""生成 v2 评测 QA 数据集（Week 2）。

运行方式（在 backend 目录）:
  python scripts/build_eval_dataset_v2.py

预期：写入 data/eval_qa_dataset_v2.json，200 条样本。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

OUTPUT = ROOT / "data" / "eval_qa_dataset_v2.json"
V1_FILE = ROOT / "data" / "eval_qa_dataset.json"

from app.core.database import async_session  # noqa: E402
from app.eval.dataset_builder_v2 import build_v2_dataset  # noqa: E402


def _v1_kb_ids() -> list[str] | None:
    if not V1_FILE.exists():
        return None
    data = json.loads(V1_FILE.read_text(encoding="utf-8"))
    kbs = data.get("knowledge_bases") or []
    ids = [k["kb_id"] for k in kbs if k.get("kb_id")]
    return ids or None


async def main() -> int:
    kb_ids = _v1_kb_ids()
    async with async_session() as db:
        data = await build_v2_dataset(db, kb_ids=kb_ids)
    samples = data["samples"]
    if len(samples) < 200:
        print(f"FAIL: expected >=200 samples, got {len(samples)}")
        return 1
    neg = sum(1 for s in samples if s["q_type"] == "negative")
    if neg < 40:
        print(f"FAIL: expected >=40 negatives, got {neg}")
        return 1
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: wrote {len(samples)} samples ({neg} negative) -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
