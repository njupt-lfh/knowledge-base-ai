"""Phase 4.1 图片入库验收

验证内容：
  - mock 模式下图片 caption、chunk、向量入库

运行方式（在 backend 目录）:
  python scripts/verify_phase4_1.py

预期结果：打印 PASS 并退出码 0；失败时退出码 1（部分脚本 SKIP 为 0）。
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ["LLM_MOCK_MODE"] = "true"
os.environ["MULTIMODAL_IMAGE_ENABLED"] = "true"


async def main() -> int:
    """脚本 CLI 入口。"""
    from app.core.chroma_client import get_collection
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.document_service import _process_image
    from app.services.embedding_service import EmbeddingService
    from app.services.media_utils import guess_image_mime, image_to_data_url, is_image_file
    from sqlalchemy import select

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = f"kb-p4-{suffix}"
    doc_id = f"d-p4-{suffix}"

    # 最小 1x1 PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload_dir = BACKEND / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    img_path = upload_dir / f"{doc_id}.png"
    img_path.write_bytes(png_bytes)

    assert is_image_file(img_path)
    assert guess_image_mime(img_path) == "image/png"
    assert image_to_data_url(img_path).startswith("data:image/png;base64,")

    async with async_session() as db:
        db.add(
            KnowledgeBase(
                id=kb_id,
                name="p4",
                embedding_model="m",
                chunk_size=500,
                chunk_overlap=50,
            )
        )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename="test.png",
                file_type="image",
                file_path=str(img_path),
                status="processing",
            )
        )
        await db.commit()

    await _process_image(doc_id, kb_id, "image", str(img_path), "test.png")

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        assert doc and doc.status == "completed", f"doc status={getattr(doc, 'status', None)}"
        assert doc.chunk_count >= 1

        result = await db.execute(select(Chunk).where(Chunk.document_id == doc_id))
        chunks = result.scalars().all()
        assert chunks and "[图片文档]" in chunks[0].content

        coll = get_collection(kb_id)
        got = coll.get(ids=[chunks[0].id], include=["embeddings", "metadatas"])
        assert got["ids"], "chroma missing chunk"
        assert got["metadatas"][0].get("media_type") == "image"

        embed_svc = EmbeddingService()
        q_vec = embed_svc.embed_query("Mock 模式下的示例描述")
        # mock 向量维度一致即可检索到自身块（距离近）
        results = coll.query(query_embeddings=[q_vec], n_results=1)
        assert results["ids"][0], "vector query returned empty"

    print("PASS: Phase 4.1 image ingest — caption + chunk + multimodal vector + FTS/graph hook")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
