"""评测基线报告 API"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/eval", tags=["eval"])

REPORT_PATH = Path(__file__).resolve().parents[3] / "data" / "eval_baseline_report.json"


@router.get("/baseline")
async def get_baseline_report():
    if not REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="baseline report not found; run run_rag_eval.py first")
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid baseline json: {exc}") from exc
