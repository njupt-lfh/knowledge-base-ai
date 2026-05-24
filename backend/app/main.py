"""AI 知识库管理平台 — FastAPI 入口"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .api import chat, chunk, document, knowledge, tag
from .core.config import settings
from .core.database import async_session, get_db, init_db


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
    from .models.document import Document

    for doc_id in body.doc_ids:
        doc = await db.get(Document, doc_id)
        if doc:
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

