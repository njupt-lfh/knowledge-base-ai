"""Temporary diagnostic for 标准普尔 retrieval issue."""

import asyncio
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "knowledge_base.db"
QUERY = "标准普尔家庭资产配置是什么？"


def inspect_db():
    if not DB.exists():
        print("DB missing:", DB)
        return []
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM knowledge_bases")
    kbs = cur.fetchall()
    print("=== Knowledge bases ===")
    for kb_id, name in kbs:
        cur.execute(
            "SELECT COUNT(*) FROM chunks WHERE knowledge_base_id=? AND is_active=1",
            (kb_id,),
        )
        n = cur.fetchone()[0]
        print(f"  {name!r} ({kb_id[:8]}…): {n} active chunks")
    targets = []
    for kb_id, name in kbs:
        if "理财" in name or "消费" in name:
            targets.append((kb_id, name))
    print("\n=== Chunks matching 标准普尔 / 资产配置 ===")
    for kb_id, name in targets or kbs:
        cur.execute(
            """
            SELECT c.id, d.filename, c.chunk_index, c.is_active, substr(c.content, 1, 100)
            FROM chunks c JOIN documents d ON c.document_id = d.id
            WHERE c.knowledge_base_id = ?
              AND (c.content LIKE '%标准普尔%' OR c.content LIKE '%资产配置%' OR c.content LIKE '%普尔%')
            LIMIT 15
            """,
            (kb_id,),
        )
        rows = cur.fetchall()
        if rows:
            print(f"\nKB: {name}")
            for row in rows:
                print(" ", row)
    conn.close()
    return targets


async def run_retrieval(kb_id: str):
    from app.core.database import async_session, init_db
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.crag_evaluator import evaluate_sufficiency
    from app.services.query_router import route_query
    from app.services.retrieval_gate import apply_retrieval_abstention

    await init_db()
    route = route_query(QUERY)
    print(f"\n=== Retrieval diag kb={kb_id[:8]}… route={route} ===")
    async with async_session() as db:
        orch = AgentOrchestrator()
        run = await orch.run(db, kb_id, QUERY)
        print(f"run.sufficient={run.sufficient} refused={run.refused} rounds={run.rounds}")
        if run.sufficiency:
            s = run.sufficiency
            print(
                f"  crag: score={s.score} max={s.max_retrieval_score} "
                f"overlap={s.term_overlap} subst={s.substantive_overlap} reason={s.reason}"
            )
        print(f"  sources count={len(run.sources)}")
        for i, src in enumerate(run.sources[:3]):
            print(
                f"  [{i}] score={src.get('score')} ce={src.get('cross_encoder_score')} "
                f"q={src.get('quality_score')} preview={src.get('content', '')[:60]!r}"
            )

        # raw hybrid without abstention path
        hybrid = await orch.hybrid.search(db, kb_id, QUERY, top_k=5)
        print(f"\n  hybrid raw: {len(hybrid)} hits")
        for i, src in enumerate(hybrid[:3]):
            print(f"  h[{i}] score={src.get('score')} {src.get('content', '')[:60]!r}")
        gated = apply_retrieval_abstention(QUERY, hybrid, route)
        print(f"  after abstention gate: {len(gated)} hits")
        ev = evaluate_sufficiency(QUERY, hybrid, route)
        print(f"  crag on hybrid: sufficient={ev.sufficient} reason={ev.reason}")


async def main():
    targets = inspect_db()
    if not targets:
        print("No finance KB found, skipping retrieval")
        return
    kb_id = targets[0][0]
    await run_retrieval(kb_id)


if __name__ == "__main__":
    asyncio.run(main())
