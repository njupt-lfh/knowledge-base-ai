"""评测集质量审计（Week 2）。

检查模板化套话、负例子类型、多 relevant 标注等。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.eval.dataset_builder_v2 import BANNED_PHRASES  # noqa: E402

DATA_V1 = ROOT / "data" / "eval_qa_dataset.json"
DATA_V2 = ROOT / "data" / "eval_qa_dataset_v2.json"


def export_review_sample(
    samples: list[dict],
    *,
    fraction: float = 0.2,
    seed: int = 42,
) -> list[dict]:
    """分层抽取人工抽检样本（默认 20%）。"""
    import random
    from collections import defaultdict

    by_type: dict[str, list[dict]] = defaultdict(list)
    for s in samples:
        by_type[s.get("q_type") or "unknown"].append(s)

    rng = random.Random(seed)
    picked: list[dict] = []
    for q_type, rows in sorted(by_type.items()):
        n = max(1, int(round(len(rows) * fraction)))
        picked.extend(rng.sample(rows, min(n, len(rows))))

    return sorted(picked, key=lambda x: x.get("id", ""))


AUDIT_EXPORT_V2 = ROOT / "data" / "eval_v2_audit_sample.json"


def audit_samples(samples: list[dict], *, version: str) -> list[str]:
    """返回审计问题列表（空=通过）。"""
    issues: list[str] = []
    type_counts = Counter(s.get("q_type") for s in samples)

    for s in samples:
        q = s.get("question") or ""
        for phrase in BANNED_PHRASES:
            if phrase in q:
                issues.append(f"{s.get('id')}: banned phrase '{phrase}'")
        if s.get("q_type") != "negative" and not s.get("relevant_chunk_ids"):
            issues.append(f"{s.get('id')}: positive sample without relevant chunks")

    if version == "v2":
        neg = [s for s in samples if s.get("q_type") == "negative"]
        if len(neg) < 40:
            issues.append(f"v2 need >=40 negatives, got {len(neg)}")
        subtypes = Counter(s.get("negative_subtype") for s in neg)
        if subtypes.get("unrelated", 0) < 20:
            issues.append(f"v2 need >=20 unrelated negatives, got {subtypes.get('unrelated', 0)}")
        if subtypes.get("near_domain", 0) < 20:
            issues.append(
                f"v2 need >=20 near_domain negatives, got {subtypes.get('near_domain', 0)}"
            )
        multi_rel = sum(1 for s in samples if len(s.get("relevant_chunk_ids") or []) > 1)
        if multi_rel < 30:
            issues.append(f"v2 expect >=30 multi-relevant samples, got {multi_rel}")

    if type_counts.get("negative", 0) < 10 and version == "v1":
        issues.append("v1 need >=10 negatives total")

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit eval QA dataset quality")
    parser.add_argument("--dataset", choices=("v1", "v2"), default="v2")
    parser.add_argument(
        "--export-review",
        action="store_true",
        help="export 20%% stratified samples for manual review (v2)",
    )
    parser.add_argument("--review-fraction", type=float, default=0.2)
    args = parser.parse_args()

    path = DATA_V2 if args.dataset == "v2" else DATA_V1
    if not path.exists():
        print(f"FAIL: missing {path}")
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    samples = data.get("samples", [])
    issues = audit_samples(samples, version=args.dataset)
    if issues:
        for i in issues[:20]:
            print(f"WARN: {i}")
        if len(issues) > 20:
            print(f"WARN: ... and {len(issues) - 20} more")
        print(f"FAIL: audit found {len(issues)} issues")
        return 1

    print(f"PASS: audit {args.dataset} ({len(samples)} samples)")

    if args.export_review and args.dataset == "v2":
        review = export_review_sample(samples, fraction=args.review_fraction)
        payload = {
            "dataset_version": "v2",
            "review_fraction": args.review_fraction,
            "sample_count": len(review),
            "instructions": "人工审核 question 自然度、relevant_chunk_ids 与 ground_truth 是否一致",
            "samples": review,
        }
        AUDIT_EXPORT_V2.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"PASS: exported {len(review)} review samples -> {AUDIT_EXPORT_V2}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
