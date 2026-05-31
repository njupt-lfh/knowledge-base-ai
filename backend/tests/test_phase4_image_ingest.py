"""Phase 4.1 图片入库 — mock 集成测试"""

import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ["LLM_MOCK_MODE"] = "true"


@pytest.mark.asyncio
async def test_process_image_creates_chunk_and_vector():
    from app.core.chroma_client import get_collection
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.document_service import _process_image
    from app.services.embedding_service import EmbeddingService
    from sqlalchemy import select

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-t4-{suffix}"
    doc_id = f"d-t4-{suffix}"

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img = Path("data/uploads") / f"{doc_id}.png"
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(png)

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="t",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="cap.png",
                file_type="image",
                file_path=str(img),
                status="processing",
            )
        )
        await db.commit()

    with (
        patch(
            "app.services.vision_caption_service.describe_image",
            new=AsyncMock(return_value="测试图片描述：流程图与指标。"),
        ),
        patch.object(
            EmbeddingService,
            "embed_image",
            return_value=[float(i % 17) for i in range(256)],
        ),
    ):
        await _process_image(doc_id, kb_id, "image", str(img), "cap.png")

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        assert doc.status == "completed"
        chunks = (
            (await db.execute(select(Chunk).where(Chunk.document_id == doc_id))).scalars().all()
        )
        assert len(chunks) == 1
        assert "Mock 描述" in chunks[0].content or "流程图" in chunks[0].content

        meta = get_collection(kb_id).get(ids=[chunks[0].id], include=["metadatas"])
        assert meta["metadatas"][0]["media_type"] == "image"
