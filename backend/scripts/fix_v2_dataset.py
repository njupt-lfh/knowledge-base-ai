"""修复 v2 评测数据集的标注问题。

对每条 fact 题，验证 primary chunk 是否真的包含答案相关内容。
标注不匹配的题目标记为 review_needed，export 供人工审核。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR.parent / "data"

V2_PATH = DATA_DIR / "eval_qa_dataset_v2.json"
V2_FIXED_PATH = DATA_DIR / "eval_qa_dataset_v2_fixed.json"
DB_PATH = DATA_DIR / "knowledge_base.db"


def check_chunk_relevance(question: str, chunk_content: str) -> tuple[bool, str]:
    """简单启发式检查 chunk 是否与问题相关。

    返回 (is_relevant, reason)
    """
    q_chars = [c for c in question if '一' <= c <= '鿿']
    if not q_chars:
        return True, "non-chinese question, skip"

    # 统计问题中文字符在 chunk 中的命中数
    hits = sum(1 for c in q_chars if c in chunk_content)
    ratio = hits / len(q_chars) if q_chars else 0

    if ratio < 0.15:
        return False, f"char overlap {ratio:.2f} < 0.15"
    if hits < 3:
        return False, f"only {hits} char hits"

    return True, f"ok (overlap={ratio:.2f}, hits={hits})"


def main():
    if not V2_PATH.exists():
        print(f"v2 dataset not found: {V2_PATH}")
        return 1

    with open(V2_PATH, encoding="utf-8") as f:
        v2 = json.load(f)

    conn = sqlite3.connect(str(DB_PATH))

    fixed_count = 0
    bad_count = 0
    review_items = []

    for sample in v2["samples"]:
        if sample["q_type"] != "fact":
            continue

        # Find primary chunk
        grades = sample.get("relevance_grades", {})
        primary_id = None
        for cid, grade in grades.items():
            if grade == "primary":
                primary_id = cid
                break

        if not primary_id:
            sample["_review"] = "no primary chunk"
            review_items.append(sample["id"])
            bad_count += 1
            continue

        row = conn.execute(
            "SELECT content FROM chunks WHERE id=?", (primary_id,)
        ).fetchone()
        if not row:
            sample["_review"] = "primary chunk not in DB"
            review_items.append(sample["id"])
            bad_count += 1
            continue

        is_ok, reason = check_chunk_relevance(sample["question"], row[0])
        if is_ok:
            fixed_count += 1
        else:
            sample["_review"] = reason
            review_items.append(sample["id"])
            bad_count += 1

    conn.close()

    # Write fixed version (all samples, bad ones marked for review)
    with open(V2_FIXED_PATH, "w", encoding="utf-8") as f:
        json.dump(v2, f, ensure_ascii=False, indent=2)

    total = fixed_count + bad_count
    print(f"v2 fact questions: {total} total")
    print(f"  OK:        {fixed_count} ({fixed_count / total * 100:.0f}%)")
    print(f"  Need fix:  {bad_count} ({bad_count / total * 100:.0f}%)")
    print(f"  Review IDs: {review_items[:10]}{'...' if len(review_items) > 10 else ''}")
    print(f"\nWritten: {V2_FIXED_PATH}")
    print(f"Next: review marked samples, fix annotations, rename to {V2_PATH.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
