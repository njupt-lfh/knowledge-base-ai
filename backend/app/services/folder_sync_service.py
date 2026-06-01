"""文件夹增量同步服务（Phase 4.4）。

职责：
    监听本地文件夹，增量导入/更新 PDF/MD/TXT/图片到知识库，
    文件变更时重置 chunk 并重新走完整入库流水线。

在流水线中的位置：
    定时任务 / API sync → scan_watch / scan_all_enabled_watches

依赖服务：
    - document_service._process_document / _process_image
"""

from __future__ import annotations

import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.document import Document
from ..models.kb_folder_watch import KbFolderWatch
from ..services.media_utils import IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)

SYNC_EXTENSIONS = {".pdf", ".md", ".txt"} | IMAGE_EXTENSIONS


@dataclass
class SyncScanResult:
    """单次文件夹扫描结果。"""

    watch_id: str
    kb_id: str
    scanned: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] | None = None


def _iter_sync_files(folder: Path, *, recursive: bool) -> list[Path]:
    """遍历目录下可同步的文件。

    参数:
        folder: 根目录
        recursive: 是否递归子目录

    返回:
        文件 Path 列表
    """
    if not folder.is_dir():
        return []
    pattern = "**/*" if recursive else "*"
    files: list[Path] = []
    for p in folder.glob(pattern):
        if p.is_file() and p.suffix.lower() in SYNC_EXTENSIONS:
            files.append(p)
    return files


async def _reset_document_chunks(db: AsyncSession, doc: Document, kb_id: str) -> None:
    """重新同步前清空文档 chunk 与 Chroma 向量。

    参数:
        db: 数据库会话
        doc: 文档实体
        kb_id: 知识库 ID
    """
    from sqlalchemy import delete

    from ..core.chroma_client import get_collection
    from ..models.chunk import Chunk

    result = await db.execute(select(Chunk).where(Chunk.document_id == doc.id))
    chunks = result.scalars().all()
    if chunks:
        try:
            get_collection(kb_id).delete(ids=[c.id for c in chunks])
        except Exception:
            logger.debug("chroma delete on resync skipped", exc_info=True)
        await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    doc.chunk_count = 0
    doc.char_count = 0
    doc.ingest_duplicate_count = 0
    doc.ingest_conflict_count = 0


async def scan_watch(
    db: AsyncSession,
    watch: KbFolderWatch,
) -> SyncScanResult:
    """扫描监听目录，新增或更新有变化的文件。

    参数:
        db: 数据库会话
        watch: 文件夹监听配置

    返回:
        SyncScanResult 扫描统计
    """
    from .document_service import _process_document, _process_image

    result = SyncScanResult(watch_id=watch.id, kb_id=watch.knowledge_base_id, errors=[])
    folder = Path(watch.folder_path)
    if not folder.is_dir():
        result.errors.append(f"目录不存在: {folder}")
        watch.last_error = result.errors[-1]
        watch.last_scan_at = datetime.utcnow()
        await db.commit()
        return result

    files = _iter_sync_files(folder, recursive=watch.recursive)
    result.scanned = len(files)

    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        from ..core.config import BASE_DIR

        upload_root = BASE_DIR / upload_root
    upload_root.mkdir(parents=True, exist_ok=True)

    existing = await db.execute(
        select(Document).where(Document.knowledge_base_id == watch.knowledge_base_id)
    )
    by_name: dict[str, Document] = {}
    for doc in existing.scalars().all():
        by_name[doc.filename] = doc

    for src in files:
        try:
            mtime = src.stat().st_mtime
            doc = by_name.get(src.name)
            if doc and doc.file_path and Path(doc.file_path).exists():
                if mtime <= Path(doc.file_path).stat().st_mtime and doc.status == "completed":
                    result.skipped += 1
                    continue

            ext = src.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                file_type = "image"
            else:
                file_type = {".pdf": "pdf", ".md": "md", ".txt": "txt"}.get(ext, "txt")

            if doc:
                doc_id = doc.id
                dest = Path(doc.file_path) if doc.file_path else upload_root / f"{doc_id}{ext}"
                await _reset_document_chunks(db, doc, watch.knowledge_base_id)
                result.updated += 1
            else:
                doc_id = str(uuid.uuid4())
                dest = upload_root / f"{doc_id}{ext}"
                doc = Document(
                    id=doc_id,
                    knowledge_base_id=watch.knowledge_base_id,
                    filename=src.name,
                    file_type=file_type,
                    file_path=str(dest),
                    file_size=src.stat().st_size,
                    status="processing",
                )
                db.add(doc)
                by_name[src.name] = doc
                result.imported += 1

            shutil.copy2(src, dest)
            doc.status = "processing"
            doc.file_size = src.stat().st_size
            doc.file_path = str(dest)
            await db.commit()

            if file_type == "image":
                await _process_image(
                    doc_id, watch.knowledge_base_id, file_type, str(dest), src.name
                )
            else:
                await _process_document(doc_id, watch.knowledge_base_id, file_type, str(dest))

        except Exception as e:
            logger.exception("sync file failed %s", src)
            result.errors.append(f"{src.name}: {e}")

    watch.last_scan_at = datetime.utcnow()
    watch.last_error = "; ".join(result.errors[:3]) if result.errors else None
    await db.commit()
    return result


async def scan_all_enabled_watches(db: AsyncSession) -> list[SyncScanResult]:
    """扫描全部启用的文件夹监听。

    参数:
        db: 数据库会话

    返回:
        各 watch 的 SyncScanResult 列表
    """
    rows = (
        (await db.execute(select(KbFolderWatch).where(KbFolderWatch.enabled.is_(True))))
        .scalars()
        .all()
    )
    return [await scan_watch(db, w) for w in rows]


async def scan_kb_watch(db: AsyncSession, kb_id: str) -> list[SyncScanResult]:
    """扫描指定知识库下启用的文件夹监听。

    参数:
        db: 数据库会话
        kb_id: 知识库 ID

    返回:
        SyncScanResult 列表
    """
    rows = (
        (
            await db.execute(
                select(KbFolderWatch).where(
                    KbFolderWatch.knowledge_base_id == kb_id,
                    KbFolderWatch.enabled.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return [await scan_watch(db, w) for w in rows]
