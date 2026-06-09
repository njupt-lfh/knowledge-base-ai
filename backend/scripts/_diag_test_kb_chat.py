"""诊断「测试」知识库最新对话拒答原因。"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
DB = ROOT / "data" / "knowledge_base.db"


def sql_rows(conn, q, params=()):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(q, params)]


async def main():
    conn = sqlite3.connect(DB)

    kbs = sql_rows(
        conn,
        "SELECT id, name FROM knowledge_bases WHERE name LIKE ? ORDER BY name",
        ("%测试%",),
    )
    if not kbs:
        kbs = sql_rows(conn, "SELECT id, name FROM knowledge_bases ORDER BY name")
    print("=== 知识库 ===")
    for kb in kbs:
        print(f"  {kb['id']}  {kb['name']}")

    target = next((k for k in kbs if k["name"] == "测试"), kbs[0] if kbs else None)
    if not target:
        print("no kb")
        return
    kb_id = target["id"]
    print(f"\n>>> 选用: {target['name']} ({kb_id})")

    convs = sql_rows(
        conn,
        """
        SELECT c.id, c.title, c.created_at,
               (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS msg_count
        FROM conversations c
        WHERE c.knowledge_base_id = ?
        ORDER BY c.created_at DESC
        LIMIT 5
        """,
        (kb_id,),
    )
    print("\n=== 最近 5 个对话 ===")
    for c in convs:
        print(
            f"  {c['created_at']}  {c['id'][:8]}…  msgs={c['msg_count']}  {c['title'] or '(无标题)'}"
        )

    if not convs:
        conn.close()
        return

    conv_id = convs[0]["id"]
    msgs = sql_rows(
        conn,
        """
        SELECT id, role, content, sources, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at DESC
        LIMIT 6
        """,
        (conv_id,),
    )
    print(f"\n=== 最新对话消息 ({conv_id}) ===")
    for m in reversed(msgs):
        src = m.get("sources")
        src_n = 0
        if src:
            try:
                src_n = len(json.loads(src))
            except Exception:
                src_n = -1
        preview = (m["content"] or "")[:200].replace("\n", " ")
        print(f"\n[{m['role']}] {m['created_at']}")
        print(f"  sources={src_n}  {preview}")

    # latest user question
    user_q = next((m for m in msgs if m["role"] == "user"), None)
    query = user_q["content"] if user_q else ""
    print(f"\n=== 最新用户问题 ===\n{query}")

    docs = sql_rows(
        conn,
        """
        SELECT id, filename, status, is_active, chunk_count
        FROM documents
        WHERE knowledge_base_id = ?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (kb_id,),
    )
    print("\n=== 文档 (最近10) ===")
    for d in docs:
        print(
            f"  {d['status']:12} active={d['is_active']} chunks={d['chunk_count']}  {d['filename'][:60]}"
        )

    conn.close()

    if not query:
        return

    # RAG 诊断
    from app.core.database import async_session, init_db
    from app.services.rag_service import RAGService

    await init_db()
    async with async_session() as db:
        rag = RAGService()
        sources = await rag.retrieve(kb_id, query, top_k=8, db=db)
        print(f"\n=== RAG retrieve top={len(sources)} ===")
        for i, s in enumerate(sources[:8], 1):
            print(
                f"  {i}. score={s.get('score'):.4f} ce={s.get('cross_encoder_score')} "
                f"doc={str(s.get('document_id', ''))[:8]} chunk={str(s.get('chunk_id', ''))[:8]}"
            )
            print(f"     {(s.get('content') or '')[:120]}")

        from app.services.agent_orchestrator import AgentOrchestrator

        orch = AgentOrchestrator()
        run = await orch.prepare_run(db, kb_id, query, history=[], top_k=8)
        print("\n=== Agent prepare_run ===")
        print(
            f"  route={run.route} skipped_retrieval={run.skipped_retrieval} refused={run.refused}"
        )
        print(f"  sources_after_pipeline={len(run.sources)}")
        if run.sources:
            for i, s in enumerate(run.sources[:3], 1):
                print(f"  {i}. score={s.get('score')} {(s.get('content') or '')[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
