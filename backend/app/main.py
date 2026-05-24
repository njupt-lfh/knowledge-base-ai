"""AI 知识库管理平台 — FastAPI 入口"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .api import chat, chunk, document, knowledge, tag
from .core.config import settings
from .core.database import get_db, init_db


class BatchStatusBody(BaseModel):
    doc_ids: list[str]
    is_active: bool


class BatchDeleteBody(BaseModel):
    doc_ids: list[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge.router)
app.include_router(chunk.router)
app.include_router(chat.router)
app.include_router(tag.router)

# 批量操作端点必须在 document.router 之前注册
# 否则 PUT /{doc_id}/status 会抢先匹配 /batch/status
@app.put("/api/knowledge-bases/{kb_id}/documents/batch/status")
async def batch_toggle_status(kb_id: str, body: BatchStatusBody, db: AsyncSession = Depends(get_db)):
    from .models.document import Document

    for doc_id in body.doc_ids:
        doc = await db.get(Document, doc_id)
        if doc:
            doc.is_active = body.is_active
    await db.commit()
    return {"ok": True, "count": len(body.doc_ids)}


@app.delete("/api/knowledge-bases/{kb_id}/documents/batch")
async def batch_delete_documents(kb_id: str, body: BatchDeleteBody, db: AsyncSession = Depends(get_db)):
    from .core.chroma_client import get_collection
    from .models.chunk import Chunk
    from .models.document import Document

    for doc_id in body.doc_ids:
        doc = await db.get(Document, doc_id)
        if doc:
            # 清理 Chroma 向量
            try:
                result = await db.execute(select(Chunk.id).where(Chunk.document_id == doc_id))
                chunk_ids = [r[0] for r in result.all()]
                if chunk_ids:
                    collection = get_collection(kb_id)
                    collection.delete(ids=chunk_ids)
            except Exception:
                pass
            # 清理上传文件
            if doc.file_path:
                from pathlib import Path
                try:
                    Path(doc.file_path).unlink(missing_ok=True)
                except Exception:
                    pass
            await db.delete(doc)
    await db.commit()
    return {"ok": True, "count": len(body.doc_ids)}


@app.get("/api/knowledge-bases/{kb_id}/documents/batch/tags")
async def batch_get_document_tags(
    kb_id: str,
    doc_ids: str = "",
    db: AsyncSession = Depends(get_db),
):
    from .models.tag import DocumentTag, Tag

    ids = [i.strip() for i in doc_ids.split(",") if i.strip()]
    if not ids:
        return {}
    result = await db.execute(
        select(DocumentTag.document_id, Tag.name)
        .join(Tag, Tag.id == DocumentTag.tag_id)
        .where(DocumentTag.document_id.in_(ids))
    )
    tag_map: dict[str, list[str]] = {did: [] for did in ids}
    for doc_id, tag_name in result:
        tag_map[doc_id].append(tag_name)
    return tag_map

app.include_router(document.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


# ——— 统计端点（T6.1）———


@app.get("/api/knowledge-bases/{kb_id}/stats")
async def knowledge_stats(kb_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import desc, func

    from .models.chunk import Chunk
    from .models.document import Document

    doc_total = (await db.execute(
        select(func.count(Document.id)).where(Document.knowledge_base_id == kb_id)
    )).scalar() or 0

    chunk_total = (await db.execute(
        select(func.count(Chunk.id)).where(Chunk.knowledge_base_id == kb_id)
    )).scalar() or 0

    total_hits = (await db.execute(
        select(func.sum(Chunk.hit_count)).where(Chunk.knowledge_base_id == kb_id)
    )).scalar() or 0

    top_chunks = (await db.execute(
        select(Chunk.id, Chunk.content, Chunk.hit_count, Chunk.chunk_index, Chunk.document_id)
        .where(Chunk.knowledge_base_id == kb_id, Chunk.hit_count > 0)
        .order_by(desc(Chunk.hit_count))
        .limit(10)
    )).all()

    hot_items = [
        {
            "chunk_id": r.id,
            "content": r.content[:100],
            "hit_count": r.hit_count,
            "chunk_index": r.chunk_index,
            "document_id": r.document_id,
        }
        for r in top_chunks
    ]

    return {
        "document_count": doc_total,
        "chunk_count": chunk_total,
        "total_hits": total_hits,
        "hot_items": hot_items,
    }


@app.get("/api/stats/overview")
async def stats_overview(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import desc, func

    from .models.chunk import Chunk
    from .models.document import Document
    from .models.knowledge_base import KnowledgeBase

    kb_count = (await db.execute(select(func.count(KnowledgeBase.id)))).scalar() or 0
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    chunk_count = (await db.execute(select(func.count(Chunk.id)))).scalar() or 0
    total_hits = (await db.execute(select(func.sum(Chunk.hit_count)))).scalar() or 0

    top = (await db.execute(
        select(Chunk.content, Chunk.hit_count, Chunk.knowledge_base_id)
        .where(Chunk.hit_count > 0)
        .order_by(desc(Chunk.hit_count))
        .limit(5)
    )).all()

    return {
        "kb_count": kb_count,
        "doc_count": doc_count,
        "chunk_count": chunk_count,
        "total_hits": total_hits,
        "top_chunks": [{"content": r.content[:80], "hits": r.hit_count} for r in top],
    }

