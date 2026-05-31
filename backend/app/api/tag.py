"""标签 API 路由"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.tag import DocumentTag, Tag

router = APIRouter(tags=["标签"])


@router.get("/api/knowledge-bases/{kb_id}/tags")
async def list_tags(kb_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).where(Tag.knowledge_base_id == kb_id))
    return [{"id": t.id, "name": t.name} for t in result.scalars().all()]


@router.post("/api/knowledge-bases/{kb_id}/tags", status_code=201)
async def create_tag(kb_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="标签名不能为空")
    tag = Tag(knowledge_base_id=kb_id, name=name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return {"id": tag.id, "name": tag.name}


@router.delete("/api/knowledge-bases/{kb_id}/tags/{tag_id}", status_code=204)
async def delete_tag(kb_id: str, tag_id: str, db: AsyncSession = Depends(get_db)):
    tag = await db.get(Tag, tag_id)
    if tag:
        await db.execute(delete(DocumentTag).where(DocumentTag.tag_id == tag_id))
        await db.delete(tag)
        await db.commit()


@router.get("/api/knowledge-bases/{kb_id}/documents/{doc_id}/tags")
async def get_document_tags(kb_id: str, doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tag)
        .join(DocumentTag, DocumentTag.tag_id == Tag.id)
        .where(DocumentTag.document_id == doc_id)
    )
    return [{"id": t.id, "name": t.name} for t in result.scalars().all()]


@router.post("/api/knowledge-bases/{kb_id}/documents/{doc_id}/tags")
async def set_document_tags(
    kb_id: str, doc_id: str, data: dict, db: AsyncSession = Depends(get_db)
):
    tag_ids = data.get("tag_ids", [])
    await db.execute(delete(DocumentTag).where(DocumentTag.document_id == doc_id))
    for tag_id in tag_ids:
        dt = DocumentTag(document_id=doc_id, tag_id=tag_id)
        db.add(dt)
    await db.commit()
    return {"tag_ids": tag_ids}
