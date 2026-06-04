"""Phase 2.4 验收：DeepEval 模块 + CI 门禁。

验证内容：
  - offline 代理指标与 deepeval gates 通过
  - knowledge retention 回归检测
  - run_deepeval_ci.py 子进程成功

运行方式（在 backend 目录）:
  python scripts/verify_phase2_4.py

预期结果：打印 PASS 并退出码 0。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    """执行 Phase 2.4 验收：DeepEval offline 指标与 CI 脚本。"""
    from app.eval.deepeval_runner import (
        check_deepeval_gates,
        check_knowledge_retention,
        offline_contextual_relevancy,
        offline_hallucination_score,
        run_deepeval,
    )

    smoke_path = BACKEND / "tests" / "fixtures" / "eval_smoke_samples.json"
    if not smoke_path.exists():
        print("FAIL: missing eval_smoke_samples.json")
        return 1

    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    scores = run_deepeval(smoke, prefer_live=False)
    gates = check_deepeval_gates(scores)
    if not gates["passed"]:
        print(f"FAIL: deepeval gates {gates}")
        return 1
    print(f"  deepeval offline gates ok (h={scores.get('hallucination_mean')})")

    rel = offline_contextual_relevancy("RAG 检索", ["RAG 检索增强生成技术说明"])
    if rel < 0.3:
        print(f"FAIL: contextual relevancy proxy {rel}")
        return 1

    hall = offline_hallucination_score(
        "RAG 是检索增强生成",
        ["RAG Retrieval Augmented Generation 检索增强生成"],
    )
    if hall < 0.3:
        print(f"FAIL: hallucination proxy {hall}")
        return 1

    # retention：小幅下降应通过
    retention = check_knowledge_retention(
        {"context_recall_mean": 0.8, "context_precision_mean": 0.3},
        {"context_recall_mean": 0.75, "context_precision_mean": 0.28},
        min_recall_ratio=0.85,
    )
    if not retention["passed"]:
        print(f"FAIL: retention should pass at 0.75/0.8 {retention}")
        return 1

    # retention：大幅下降应失败
    retention_fail = check_knowledge_retention(
        {"context_recall_mean": 0.8},
        {"context_recall_mean": 0.5},
        min_recall_ratio=0.85,
    )
    if retention_fail["passed"]:
        print("FAIL: retention should fail on big drop")
        return 1

    import subprocess

    proc = subprocess.run(
        [sys.executable, str(BACKEND / "scripts" / "run_deepeval_ci.py")],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        print(f"FAIL: run_deepeval_ci.py\n{proc.stdout}\n{proc.stderr}")
        return 1
    print("  run_deepeval_ci.py ok")

    print("PASS: Phase 2.4 — DeepEval CI gates + Knowledge Retention")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
