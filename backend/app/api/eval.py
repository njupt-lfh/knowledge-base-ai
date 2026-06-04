"""评测基线报告 API 路由。

只读暴露本地 JSON 评测基线文件与 DB 历史趋势，
需先运行 `run_rag_eval.py` 生成报告文件。
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.eval_run_service import get_eval_run, list_eval_runs, metric_trend

router = APIRouter(prefix="/api/eval", tags=["eval"])

REPORT_PATH = Path(__file__).resolve().parents[3] / "data" / "eval_baseline_report.json"
PHASE0_PATH = Path(__file__).resolve().parents[3] / "data" / "eval_baseline_report_phase0.json"


@router.get("/baseline")
async def get_baseline_report():
    """读取当前评测基线 JSON 报告。"""
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
    """读取 Phase 0 备份基线 JSON 报告。"""
    if not PHASE0_PATH.exists():
        raise HTTPException(status_code=404, detail="phase0 backup not found")
    try:
        return json.loads(PHASE0_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid phase0 json: {exc}") from exc


@router.get("/runs")
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """最近评测运行列表（DB）。"""
    return {"runs": await list_eval_runs(db, limit=limit)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """单次评测运行完整报告。"""
    report = await get_eval_run(db, run_id)
    if not report:
        raise HTTPException(status_code=404, detail="eval run not found")
    return report


@router.get("/trend/{metric}")
async def get_metric_trend(
    metric: str,
    limit: int = Query(20, ge=1, le=100),
    dataset: str | None = Query(None, description="v1 or v2"),
    db: AsyncSession = Depends(get_db),
):
    """指标历史趋势。"""
    points = await metric_trend(db, metric, limit=limit, dataset_version=dataset)
    return {"metric": metric, "points": points}
