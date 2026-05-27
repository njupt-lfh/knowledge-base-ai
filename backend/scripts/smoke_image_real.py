"""真实 API 图片入库联调 — 用法: python scripts/smoke_image_real.py <图片路径> [kb_id]"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path", type=Path)
    parser.add_argument("kb_id", nargs="?", default="")
    args = parser.parse_args()

    img_src: Path = args.image_path
    if not img_src.is_file():
        print(f"FAIL: 文件不存在: {img_src}")
        return 1

    if settings.LLM_MOCK_MODE:
        print("FAIL: LLM_MOCK_MODE=true，请改为 false 后再联调")
        return 1
    if not settings.MULTIMODAL_IMAGE_ENABLED:
        print("FAIL: MULTIMODAL_IMAGE_ENABLED=false")
        return 1

    from sqlalchemy import select

    from app.core.chroma_client import get_collection
    from app.core.database import async_session, init_db
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.services.document_service import _process_image
    from app.services.embedding_service import EmbeddingService

    await init_db()
    suffix = uuid.uuid4().hex[:8]
    kb_id = args.kb_id.strip() or f"kb-smoke-p4-{suffix}"
    doc_id = f"d-smoke-p4-{suffix}"
    ext = img_src.suffix.lower() or ".png"

    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.is_absolute():
        upload_dir = BACKEND / upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{doc_id}{ext}"
    shutil.copy2(img_src, dest)

    print(f"源图: {img_src} ({img_src.stat().st_size} bytes)")
    print(f"复制: {dest}")
    print(f"LLM: {settings.VOLCENGINE_LLM_MODEL}")
    print(f"Embedding: {settings.VOLCENGINE_EMBEDDING_MODEL}")
    vision = (settings.VISION_CAPTION_MODEL or "").strip() or settings.VOLCENGINE_LLM_MODEL
    print(f"Vision caption: {vision}")

    async with async_session() as db:
        if args.kb_id.strip():
            kb = await db.get(KnowledgeBase, kb_id)
            if not kb:
                print(f"FAIL: 知识库不存在: {kb_id}")
                return 1
        else:
            db.add(
                KnowledgeBase(
                    id=kb_id,
                    name=f"图片联调-{suffix}",
                    embedding_model=settings.VOLCENGINE_EMBEDDING_MODEL,
                    chunk_size=500,
                    chunk_overlap=50,
                )
            )
        db.add(
            Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                filename=img_src.name,
                file_type="image",
                file_path=str(dest),
                file_size=img_src.stat().st_size,
                status="processing",
            )
        )
        await db.commit()

    print("处理中（Vision + embed_image，约 10–30s）...")
    await _process_image(doc_id, kb_id, "image", str(dest), img_src.name)

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if not doc or doc.status != "completed":
            print(f"FAIL: 文档状态={getattr(doc, 'status', None)}")
            return 1

        chunks = (
            await db.execute(select(Chunk).where(Chunk.document_id == doc_id))
        ).scalars().all()
        if not chunks:
            print("FAIL: 无 chunk")
            return 1

        c = chunks[0]
        print("\n--- Chunk 内容 ---")
        print(c.content)
        print(f"\n字符数: {len(c.content)} | chunk_id: {c.id}")

        coll = get_collection(kb_id)
        got = coll.get(ids=[c.id], include=["embeddings", "metadatas", "documents"])
        meta = (got.get("metadatas") or [None])[0] or {}
        embs = got.get("embeddings")
        emb = embs[0] if embs is not None and len(embs) > 0 else []
        print(f"\nChroma: media_type={meta.get('media_type')} dim={len(emb)}")

        # 检索：用「孔子」相关 query
        queries = ["孔子", "图中人物", "儒家"]
        embed_svc = EmbeddingService()
        for q in queries:
            qv = embed_svc.embed_query(q)
            res = coll.query(query_embeddings=[qv], n_results=3)
            ids = res["ids"][0] if res.get("ids") else []
            dists = res["distances"][0] if res.get("distances") else []
            hit = c.id in ids
            rank = ids.index(c.id) + 1 if hit else "-"
            dist = dists[ids.index(c.id)] if hit else None
            print(f"检索「{q}」: hit={hit} rank={rank} distance={dist}")

    print(f"\nPASS: 真实图片入库联调完成 kb_id={kb_id} doc_id={doc_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
