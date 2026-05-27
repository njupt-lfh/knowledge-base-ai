"""Phase 2.2 验收：Agentic-lite Router + CRAG-lite + 拒答"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


async def main() -> int:
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from app.core.database import async_session, init_db
    from app.main import app
    from app.models.knowledge_base import KnowledgeBase
    from app.services.agent_orchestrator import REFUSAL_TEXT, AgentOrchestrator
    from app.services.crag_evaluator import evaluate_sufficiency
    from app.services.query_router import route_query

    await init_db()

    if route_query("Python 和 Java 的区别") != "relational":
        print("FAIL: query router relational")
        return 1

    if route_query("你好") != "chitchat":
        print("FAIL: query router chitchat")
        return 1

    weak = evaluate_sufficiency("冷门", [{"content": "无关", "score": 0.01}], "factual")
    if weak.sufficient:
        print("FAIL: CRAG should reject weak sources")
        return 1

    orch = AgentOrchestrator()
    async with async_session() as db:
        kb = (await db.execute(select(KnowledgeBase).limit(1))).scalar_one_or_none()
        if kb:
            run = await orch.run(db, kb.id, "xyznonexistent_topic_999", top_k=3)
            if not run.refused:
                print(f"FAIL: expected refusal, got sufficient={run.sufficient}")
                return 1
            print(f"  crag refusal ok (rounds={run.rounds}, reason={run.sufficiency.reason if run.sufficiency else ''})")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if kb:
            conv = await client.post(f"/api/knowledge-bases/{kb.id}/chat")
            if conv.status_code != 201:
                print(f"FAIL: create conversation {conv.status_code}")
                return 1
            conv_id = conv.json()["id"]

            collected = ""
            async with client.stream(
                "POST",
                f"/api/conversations/{conv_id}/chat",
                json={"message": "xyznonexistent_topic_999", "knowledge_base_id": kb.id},
            ) as resp:
                if resp.status_code != 200:
                    print(f"FAIL: chat stream {resp.status_code}")
                    return 1
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = json.loads(line[6:])
                    if payload.get("type") == "text":
                        collected += payload.get("content", "")

            if REFUSAL_TEXT[:10] not in collected and "暂无相关信息" not in collected:
                print(f"FAIL: chat did not refuse: {collected[:120]}")
                return 1
            print("  chat refusal stream ok")

    print("PASS: Phase 2.2 — Agentic-lite Router + CRAG-lite + Refusal")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
