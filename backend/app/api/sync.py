"""增量同步 API — Phase 4.4 文件夹监听 / Webhook"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..models.kb_folder_watch import KbFolderWatch
from ..services.folder_sync_service import scan_all_enabled_watches, scan_kb_watch, scan_watch

router = APIRouter(prefix="/api/sync", tags=["增量同步"])


class FolderWatchCreate(BaseModel):
    knowledge_base_id: str
    folder_path: str
    enabled: bool = True
    recursive: bool = False


class FolderWatchUpdate(BaseModel):
    enabled: bool | None = None
    recursive: bool | None = None


class FolderWatchResponse(BaseModel):
    id: str
    knowledge_base_id: str
    folder_path: str
    enabled: bool
    recursive: bool
    last_scan_at: datetime | None = None
    last_error: str | None = None

    class Config:
        from_attributes = True


class ScanResultItem(BaseModel):
    watch_id: str
    kb_id: str
    scanned: int
    imported: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


@router.post("/watches", response_model=FolderWatchResponse, status_code=201)
async def create_watch(body: FolderWatchCreate, db: AsyncSession = Depends(get_db)):
    path = body.folder_path.strip()
    if not path:
        raise HTTPException(400, "folder_path 不能为空")
    row = KbFolderWatch(
        knowledge_base_id=body.knowledge_base_id,
        folder_path=path,
        enabled=body.enabled,
        recursive=body.recursive,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return FolderWatchResponse.model_validate(row)


@router.get("/watches", response_model=list[FolderWatchResponse])
async def list_watches(
    kb_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(KbFolderWatch)
    if kb_id:
        q = q.where(KbFolderWatch.knowledge_base_id == kb_id)
    rows = (await db.execute(q.order_by(KbFolderWatch.created_at.desc()))).scalars().all()
    return [FolderWatchResponse.model_validate(r) for r in rows]


@router.patch("/watches/{watch_id}", response_model=FolderWatchResponse)
async def update_watch(
    watch_id: str,
    body: FolderWatchUpdate,
    db: AsyncSession = Depends(get_db),
):
    watch = await db.get(KbFolderWatch, watch_id)
    if not watch:
        raise HTTPException(404, "监听配置不存在")
    if body.enabled is not None:
        watch.enabled = body.enabled
    if body.recursive is not None:
        watch.recursive = body.recursive
    await db.commit()
    await db.refresh(watch)
    return FolderWatchResponse.model_validate(watch)


@router.delete("/watches/{watch_id}", status_code=204)
async def delete_watch(watch_id: str, db: AsyncSession = Depends(get_db)):
    watch = await db.get(KbFolderWatch, watch_id)
    if not watch:
        raise HTTPException(404, "监听配置不存在")
    await db.delete(watch)
    await db.commit()


@router.post("/watches/{watch_id}/scan", response_model=ScanResultItem)
async def trigger_watch_scan(watch_id: str, db: AsyncSession = Depends(get_db)):
    watch = await db.get(KbFolderWatch, watch_id)
    if not watch:
        raise HTTPException(404, "监听配置不存在")
    r = await scan_watch(db, watch)
    return ScanResultItem(
        watch_id=r.watch_id,
        kb_id=r.kb_id,
        scanned=r.scanned,
        imported=r.imported,
        updated=r.updated,
        skipped=r.skipped,
        errors=r.errors or [],
    )


@router.post("/knowledge-bases/{kb_id}/scan", response_model=list[ScanResultItem])
async def trigger_kb_scan(kb_id: str, db: AsyncSession = Depends(get_db)):
    results = await scan_kb_watch(db, kb_id)
    return [
        ScanResultItem(
            watch_id=r.watch_id,
            kb_id=r.kb_id,
            scanned=r.scanned,
            imported=r.imported,
            updated=r.updated,
            skipped=r.skipped,
            errors=r.errors or [],
        )
        for r in results
    ]


@router.post("/webhook/{kb_id}", response_model=list[ScanResultItem])
async def webhook_sync(
    kb_id: str,
    x_sync_secret: str | None = Header(default=None, alias="X-Sync-Secret"),
    db: AsyncSession = Depends(get_db),
):
    secret = (settings.SYNC_WEBHOOK_SECRET or "").strip()
    if secret and x_sync_secret != secret:
        raise HTTPException(401, "无效的 X-Sync-Secret")
    results = await scan_kb_watch(db, kb_id)
    if not results:
        raise HTTPException(404, "该知识库未配置文件夹监听")
    return [
        ScanResultItem(
            watch_id=r.watch_id,
            kb_id=r.kb_id,
            scanned=r.scanned,
            imported=r.imported,
            updated=r.updated,
            skipped=r.skipped,
            errors=r.errors or [],
        )
        for r in results
    ]


@router.post("/scan-all", response_model=list[ScanResultItem])
async def trigger_scan_all(
    x_sync_secret: str | None = Header(default=None, alias="X-Sync-Secret"),
    db: AsyncSession = Depends(get_db),
):
    secret = (settings.SYNC_WEBHOOK_SECRET or "").strip()
    if secret and x_sync_secret != secret:
        raise HTTPException(401, "无效的 X-Sync-Secret")
    results = await scan_all_enabled_watches(db)
    return [
        ScanResultItem(
            watch_id=r.watch_id,
            kb_id=r.kb_id,
            scanned=r.scanned,
            imported=r.imported,
            updated=r.updated,
            skipped=r.skipped,
            errors=r.errors or [],
        )
        for r in results
    ]
