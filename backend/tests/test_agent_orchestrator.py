"""Phase 2.2 单元测试 — Query Router + CRAG-lite + AgentOrchestrator

验证内容：
  - Query Router、CRAG-lite、AgentOrchestrator 拒答与闲聊跳过检索

运行方式（在 backend 目录）:
  pytest tests/test_agent_orchestrator.py -v

预期结果：全部用例通过。
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.crag_evaluator import evaluate_sufficiency
from app.services.query_router import expand_query_for_retry, retrieval_top_k_for_route, route_query


def test_route_factual():
    """验证 Query Router 路由类型。"""
    assert route_query("什么是 RAG 检索增强生成") == "factual"


def test_route_relational():
    """验证 Query Router 路由类型。"""
    assert route_query("Python 和 Java 的区别是什么") == "relational"


def test_route_comprehensive():
    """验证 Query Router 路由类型。"""
    assert route_query("请总结知识库中有哪些部署方式") == "comprehensive"


def test_route_chitchat():
    """验证 Query Router 路由类型。"""
    assert route_query("你好") == "chitchat"


def test_retrieval_top_k_by_route():
    """测试：retrieval top k by route。"""
    assert retrieval_top_k_for_route("chitchat", 5) == 0
    assert retrieval_top_k_for_route("relational", 5) >= 7


def test_expand_query_for_retry():
    """测试：expand query for retry。"""
    q = expand_query_for_retry("Python 和 Java 的区别", "relational")
    assert "Python" in q or "Java" in q


def test_crag_sufficient_with_good_sources():
    """验证 CRAG 充分性判定。"""
    sources = [{"content": "RAG 是检索增强生成技术", "score": 0.45}]
    r = evaluate_sufficiency("什么是 RAG", sources, "factual")
    assert r.sufficient is True


def test_crag_insufficient_empty():
    """验证空结果路径。"""
    r = evaluate_sufficiency("量子纠错", [], "factual")
    assert r.sufficient is False


def test_crag_insufficient_weak_score():
    """验证 CRAG 充分性判定。"""
    sources = [{"content": "无关内容", "score": 0.05}]
    r = evaluate_sufficiency("深度学习框架对比", sources, "factual")
    assert r.sufficient is False


def test_crag_sufficient_rrf_scale_with_overlap():
    """RRF 分很低但词面高度重叠时，应判定为充分（修复误拒答）。"""
    sources = [
        {
            "content": (
                "Python 与 JavaScript 异步模型的核心关联与差异。"
                "两者的异步模型同源，async/await 语法由 JS 影响 Python。"
            ),
            "score": 0.03,
        }
    ]
    r = evaluate_sufficiency(
        "Python 和 JavaScript 在异步模型上有什么关联",
        sources,
        "relational",
    )
    assert r.sufficient is True
    assert r.term_overlap >= 0.12


@pytest.mark.asyncio
async def test_agent_refuses_when_crag_fails():
    """验证 CRAG 充分性判定。"""
    orch = AgentOrchestrator()
    db = AsyncMock()

    weak = [{"chunk_id": "c1", "content": "x", "score": 0.05, "document_id": "d", "chunk_index": 0}]

    with patch.object(orch.hybrid, "search", AsyncMock(return_value=weak)):
        run = await orch.run(db, "kb1", "完全不存在的冷门话题 XYZ", top_k=3)

    assert run.refused is True
    assert run.sufficient is False
    assert run.rounds == 2


@pytest.mark.asyncio
async def test_agent_skips_retrieval_for_chitchat():
    """验证 AgentOrchestrator 行为。"""
    orch = AgentOrchestrator()
    db = AsyncMock()

    with patch.object(orch.hybrid, "search", AsyncMock()) as mock_search:
        run = await orch.run(db, "kb1", "你好", top_k=5)

    mock_search.assert_not_called()
    assert run.skipped_retrieval is True
    assert run.route == "chitchat"


@pytest.mark.asyncio
async def test_agent_generate_refusal_stream():
    """验证 AgentOrchestrator 行为。"""
    orch = AgentOrchestrator()
    db = AsyncMock()

    weak = [{"chunk_id": "c1", "content": "x", "score": 0.05, "document_id": "d", "chunk_index": 0}]

    with patch.object(orch.hybrid, "search", AsyncMock(return_value=weak)):
        events = []
        async for ev in orch.generate_stream(
            db,
            "kb1",
            "冷门话题 ABC",
            [],
            system_prompt_template="ctx={context}",
            compress_context=lambda s, max_chars: "",
        ):
            events.append(ev)

    meta = json.loads([ev for ev in events if '"type": "agent_meta"' in ev][0][6:])
    assert meta.get("refused") is True

    text_payloads = []
    for ev in events:
        if '"type": "text"' in ev:
            text_payloads.append(json.loads(ev[6:]).get("content", ""))
    assert "暂无相关信息" in "".join(text_payloads)
