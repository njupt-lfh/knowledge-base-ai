"""文档标签 API 路由。

提供知识库标签 CRUD 及文档-标签关联的查询与批量设置，
直接操作 Tag / DocumentTag ORM 表。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.tag import DocumentTag, Tag

router = APIRouter(tags=["标签"])


@router.get("/api/knowledge-bases/{kb_id}/tags")
async def list_tags(kb_id: str, db: AsyncSession = Depends(get_db)):
    """列出知识库下全部标签。

    参数:
        kb_id: 知识库 ID。
        db: 数据库会话。

    返回:
        含 id、name 的标签字典列表。
    """
    result = await db.execute(select(Tag).where(Tag.knowledge_base_id == kb_id))
    return [{"id": t.id, "name": t.name} for t in result.scalars().all()]


@router.post("/api/knowledge-bases/{kb_id}/tags", status_code=201)
async def create_tag(kb_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    """创建新标签。

    参数:
        kb_id: 知识库 ID。
        data: JSON 体，需含 name 字段。
        db: 数据库会话。

    返回:
        新建标签的 id 与 name；名称为空时 400。
    """
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
    """删除标签及其全部文档关联。

    参数:
        kb_id: 知识库 ID（路径参数，未校验归属）。
        tag_id: 标签 ID。
        db: 数据库会话。
    """
    tag = await db.get(Tag, tag_id)
    if tag:
        await db.execute(delete(DocumentTag).where(DocumentTag.tag_id == tag_id))
        await db.delete(tag)
        await db.commit()


@router.get("/api/knowledge-bases/{kb_id}/documents/{doc_id}/tags")
async def get_document_tags(kb_id: str, doc_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个文档已绑定的标签列表。

    参数:
        kb_id: 知识库 ID。
        doc_id: 文档 ID。
        db: 数据库会话。

    返回:
        标签 id/name 列表。
    """
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
    """全量替换文档的标签关联（先删后增）。

    参数:
        kb_id: 知识库 ID。
        doc_id: 文档 ID。
        data: JSON 体，需含 tag_ids 数组。
        db: 数据库会话。

    返回:
        设置后的 tag_ids 列表。
    """
    tag_ids = data.get("tag_ids", [])
    await db.execute(delete(DocumentTag).where(DocumentTag.document_id == doc_id))
    for tag_id in tag_ids:
        dt = DocumentTag(document_id=doc_id, tag_id=tag_id)
        db.add(dt)
    await db.commit()
    return {"tag_ids": tag_ids}
