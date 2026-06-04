"""修复 v2 评测数据集标注。

对每条 fact 题验证 primary chunk 是否真正相关；
不相关的自动搜索更匹配的 chunk 替换。
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

DATA_DIR = BACKEND_DIR.parent / "data"
V2_PATH = DATA_DIR / "eval_qa_dataset_v2.json"
DB_PATH = DATA_DIR / "knowledge_base.db"


def extract_key_terms(text: str) -> list[str]:
    """提取中文关键词（2-4字词组）"""
    # 移除常见停用词和标点
    stop_words = {
        "什么", "如何", "为什么", "怎么", "哪些", "哪个", "请问", "请",
        "介绍", "解释", "说明", "列出", "描述", "比较", "分析",
        "一下", "一个", "一种", "这个", "那个", "可以", "需要",
        "的", "是", "在", "有", "和", "与", "或", "及", "等",
        "了", "吗", "呢", "吧", "啊", "哦", "嗯",
    }
    # 提取中文
    chinese = re.findall(r"[一-鿿]+", text)
    all_chars = "".join(chinese)

    # 生成 2-4 字词组
    terms = []
    for n in [4, 3, 2]:
        for i in range(len(all_chars) - n + 1):
            term = all_chars[i : i + n]
            if term not in stop_words:
                terms.append(term)

    # 按长度降序排列（更长的词组更精确）
    terms.sort(key=lambda t: -len(t))
    return terms[:20]  # 最多取 20 个


def check_chunk_match(question: str, chunk_content: str) -> tuple[bool, float, int]:
    """检查 chunk 是否包含问题关键信息。

    返回 (is_relevant, overlap_ratio, char_hits)
    """
    q_chars = [c for c in question if "一" <= c <= "鿿"]
    if not q_chars:
        return True, 1.0, 0

    hits = sum(1 for c in q_chars if c in chunk_content)
    ratio = hits / len(q_chars)
    return ratio >= 0.15 and hits >= 3, ratio, hits


def search_best_chunks(question: str, kb_id: str, conn, top_n: int = 3):
    """在 KB 中搜索最佳匹配 chunk。"""
    terms = extract_key_terms(question)
    q_chars = set(c for c in question if "一" <= c <= "鿿")

    candidates = {}  # chunk_id -> (content, doc_id, score)
    for term in terms[:8]:  # 用前 8 个关键词
        rows = conn.execute(
            """SELECT c.id, c.content, c.document_id
               FROM chunks c
               WHERE c.knowledge_base_id = ? AND c.is_active = 1
                 AND c.content LIKE ? LIMIT 10""",
            (kb_id, f"%{term}%"),
        ).fetchall()
        for cid, content, doc_id in rows:
            if cid in candidates:
                continue
            hits = sum(1 for c in q_chars if c in content)
            score = hits / len(q_chars) if q_chars else 0
            candidates[cid] = (content, doc_id, score)

    # 排序：先按 score 降序，同分按 chunk 长度降序
    ranked = sorted(candidates.items(), key=lambda x: -x[1][2])
    return [(cid, data[0], data[1], data[2]) for cid, data in ranked[:top_n]]


def main():
    if not V2_PATH.exists():
        print(f"Not found: {V2_PATH}")
        return 1

    with open(V2_PATH, encoding="utf-8") as f:
        v2 = json.load(f)

    conn = sqlite3.connect(str(DB_PATH))

    fixed_count = 0
    ok_count = 0
    failed_count = 0

    for sample in v2["samples"]:
        if sample["q_type"] != "fact":
            continue

        kb_id = sample["kb_id"]
        question = sample["question"]
        sample_id = sample["id"]

        # 找 primary chunk
        grades = sample.get("relevance_grades", {})
        primary_id = next(
            (cid for cid, g in grades.items() if g == "primary"), None
        )
        if not primary_id:
            primary_id = (
                sample["relevant_chunk_ids"][0]
                if sample["relevant_chunk_ids"]
                else None
            )

        if not primary_id:
            # No primary chunk at all - search
            best = search_best_chunks(question, kb_id, conn, top_n=2)
            if best:
                sample["relevant_chunk_ids"] = [best[0][0]]
                if len(best) > 1:
                    sample["relevant_chunk_ids"].append(best[1][0])
                sample["relevance_grades"] = {best[0][0]: "primary"}
                if len(best) > 1:
                    sample["relevance_grades"][best[1][0]] = "supporting"
                sample["ground_truth"] = best[0][1][:300]
                fixed_count += 1
            else:
                failed_count += 1
            continue

        # Verify existing primary chunk
        row = conn.execute(
            "SELECT content FROM chunks WHERE id=?", (primary_id,)
        ).fetchone()
        if not row:
            failed_count += 1
            continue

        is_ok, ratio, hits = check_chunk_match(question, row[0])
        if is_ok:
            ok_count += 1
            continue

        # Existing annotation is bad - try to find better
        print(f"{sample_id}: {question[:60]}")
        print(f"  old primary: ratio={ratio:.2f} hits={hits}")

        best = search_best_chunks(question, kb_id, conn, top_n=2)
        if not best or best[0][3] < 0.15:
            print(f"  FAIL: no good match found")
            failed_count += 1
            continue

        # Update annotation
        new_ids = [best[0][0]]
        new_grades = {best[0][0]: "primary"}
        if len(best) > 1:
            new_ids.append(best[1][0])
            new_grades[best[1][0]] = "supporting"

        sample["relevant_chunk_ids"] = new_ids
        sample["relevance_grades"] = new_grades
        sample["ground_truth"] = best[0][1][:300]
        sample.pop("_review", None)

        print(
            f"  FIXED: primary={best[0][0][:8]}... "
            f"score={best[0][3]:.2f}"
        )
        fixed_count += 1

    conn.close()

    # Save
    total = ok_count + fixed_count + failed_count
    v2[
        "description"
    ] = f"v2 fixed: {fixed_count} annotations corrected, {failed_count} unfixable, {ok_count} already OK"
    with open(V2_PATH, "w", encoding="utf-8") as f:
        json.dump(v2, f, ensure_ascii=False, indent=2)

    print(f"\n=== Fact Questions: {total} ===")
    print(f"Already OK:   {ok_count}")
    print(f"Fixed:         {fixed_count}")
    print(f"Could not fix: {failed_count}")
    print(f"Saved: {V2_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
