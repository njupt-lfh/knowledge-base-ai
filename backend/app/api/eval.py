"""评测基线报告 API 路由。

只读暴露本地 JSON 评测基线文件，供前端或 CI 对比 Phase 0/当前指标，
需先运行 `run_rag_eval.py` 生成报告文件。
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/eval", tags=["eval"])

REPORT_PATH = Path(__file__).resolve().parents[3] / "data" / "eval_baseline_report.json"
PHASE0_PATH = Path(__file__).resolve().parents[3] / "data" / "eval_baseline_report_phase0.json"


@router.get("/baseline")
async def get_baseline_report():
    """读取当前评测基线 JSON 报告。

    返回:
        解析后的报告字典；文件不存在时 404。
    """
    if not REPORT_PATH.exists():
        raise HTTPException(
            status_code=404, detail="baseline report not found; run run_rag_eval.py first"
        )
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid baseline json: {exc}") from exc


@router.get("/baseline-phase0")
async def get_baseline_phase0():
    """读取 Phase 0 备份基线 JSON 报告。

    返回:
        解析后的 Phase 0 报告字典；文件不存在时 404。
    """
    if not PHASE0_PATH.exists():
        raise HTTPException(status_code=404, detail="phase0 backup not found")
    try:
        return json.loads(PHASE0_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid phase0 json: {exc}") from exc
