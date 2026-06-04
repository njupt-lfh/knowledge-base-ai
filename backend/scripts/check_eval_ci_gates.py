"""CI 评测门禁检查 CLI。

运行方式:
  python scripts/check_eval_ci_gates.py --report ../data/eval_baseline_report.json --phase week2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.eval.ci_gates import check_gates  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check eval CI gates")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "data" / "eval_baseline_report.json",
    )
    parser.add_argument(
        "--phase",
        choices=("v1_baseline", "week0", "week2", "week2_v2", "week4", "week4_quality"),
        default="week0",
    )
    args = parser.parse_args()

    if not args.report.exists():
        print(f"FAIL: report not found: {args.report}")
        return 1

    report = json.loads(args.report.read_text(encoding="utf-8"))
    ok, failures = check_gates(report, args.phase)

    if ok:
        print(f"PASS: CI gates ({args.phase})")
        return 0

    print(f"FAIL: CI gates ({args.phase})")
    for f in failures:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
