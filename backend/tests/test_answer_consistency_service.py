"""答案一致性守卫单元测试（Phase 2 P0）。

含合成矛盾样本 ≥20 条，验证 check_consistency 在 LLM 判定 CONFLICT 时拒答路径。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.answer_consistency_service import (
    check_consistency,
    should_enable_consistency,
)

# 合成矛盾集：20 组 query + 互斥答案对（模拟双路径生成结果）
SYNTHETIC_CONFLICTS: list[tuple[str, str, str]] = [
    ("Python 和 Java 的主要区别是什么？", "Python 是解释型语言。", "Python 是编译型语言。"),
    ("React 18 的并发特性是什么？", "React 18 引入了 Suspense 并发渲染。", "React 18 不支持并发渲染。"),
    ("Docker 容器与虚拟机的区别？", "容器共享宿主机内核。", "容器包含完整 Guest OS 内核。"),
    ("Kubernetes 中 Pod 是什么？", "Pod 是最小调度单元。", "Pod 是节点级别的物理机。"),
    ("RAG 检索增强生成的核心步骤？", "先检索再生成。", "仅依赖参数知识，不检索。"),
    ("BERT 预训练任务有哪些？", "MLM 和 NSP。", "BERT 只做分类任务。"),
    ("SQL 中 JOIN 的作用？", "关联多表数据。", "JOIN 仅用于排序。"),
    ("HTTPS 与 HTTP 的区别？", "HTTPS 加密传输。", "HTTPS 与 HTTP 完全相同。"),
    ("微服务架构的优点？", "独立部署、弹性扩展。", "微服务必须单体部署。"),
    ("Redis 主要用途？", "内存缓存与数据结构存储。", "Redis 只能做消息队列。"),
    ("GraphQL 与 REST 的差异？", "GraphQL 客户端指定字段。", "GraphQL 固定返回全部字段。"),
    ("OAuth2 授权码模式流程？", "浏览器重定向换 token。", "OAuth2 不需要用户授权。"),
    ("Elasticsearch 倒排索引作用？", "加速全文检索。", "倒排索引用于事务 ACID。"),
    ("Transformer 自注意力机制？", "计算序列内 token 关联。", "Transformer 无注意力层。"),
    ("CI/CD 流水线目的？", "自动化构建测试部署。", "CI/CD 仅用于代码审查。"),
    ("MongoDB 文档模型特点？", "Schema 灵活 BSON 文档。", "MongoDB 仅支持固定表结构。"),
    ("Kafka 消息顺序保证？", "分区内有序。", "Kafka 全局严格有序无分区概念。"),
    ("TLS 握手主要步骤？", "协商密钥与证书验证。", "TLS 不使用证书。"),
    ("向量数据库用途？", "语义相似检索。", "向量库仅存储关系表。"),
    ("Prompt Engineering 核心原则？", "清晰指令与示例。", "Prompt 越长效果越差是唯一原则。"),
]


@pytest.mark.parametrize("query,answer_a,answer_b", SYNTHETIC_CONFLICTS)
@pytest.mark.asyncio
async def test_synthetic_conflict_llm_judge_returns_conflict(query, answer_a, answer_b):
    """合成矛盾集：LLM 判定 CONFLICT 时 check_consistency 应返回 CONFLICT。"""
    mock_llm = AsyncMock(return_value="CONFLICT")

    with patch("app.services.llm_service.LLMService") as cls:
        cls.return_value.chat_completion = mock_llm
        result = await check_consistency(query, answer_a, answer_b)

    assert result.verdict == "CONFLICT"
    assert result.answer_a == answer_a
    assert result.answer_b == answer_b


@pytest.mark.asyncio
async def test_identical_answers_ok_without_llm():
    """完全相同答案 → OK，不调用 LLM。"""
    with patch("app.services.llm_service.LLMService") as cls:
        result = await check_consistency("什么是 RAG", "RAG 是检索增强生成。", "RAG 是检索增强生成。")
        cls.assert_not_called()
    assert result.verdict == "OK"
    assert result.reason == "identical answers"


@pytest.mark.asyncio
async def test_empty_answer_uncertain():
    """任一答案为空 → UNCERTAIN。"""
    result = await check_consistency("测试", "", "有内容")
    assert result.verdict == "UNCERTAIN"


@pytest.mark.asyncio
async def test_llm_uncertain_verdict():
    """LLM 返回 UNCERTAIN。"""
    with patch("app.services.llm_service.LLMService") as cls:
        cls.return_value.chat_completion = AsyncMock(return_value="UNCERTAIN")
        result = await check_consistency(
            "复杂问题",
            "答案 A 讨论性能。",
            "答案 B 讨论部署。",
        )
    assert result.verdict == "UNCERTAIN"


@pytest.mark.asyncio
async def test_llm_ok_verdict():
    """LLM 返回 OK。"""
    with patch("app.services.llm_service.LLMService") as cls:
        cls.return_value.chat_completion = AsyncMock(return_value="OK")
        result = await check_consistency(
            "什么是 Python",
            "Python 是高级编程语言。",
            "Python 是一种高级语言，解释执行。",
        )
    assert result.verdict == "OK"


@pytest.mark.asyncio
async def test_judge_error_defaults_ok():
    """LLM 异常 → 默认放行 OK。"""
    with patch("app.services.llm_service.LLMService") as cls:
        cls.return_value.chat_completion = AsyncMock(side_effect=RuntimeError("api down"))
        result = await check_consistency("q", "a1", "a2")
    assert result.verdict == "OK"
    assert "judge error" in result.reason


def test_should_enable_consistency_relational():
    """relational 路由应启用一致性检查。"""
    with patch("app.services.answer_consistency_service.settings") as s:
        s.ANSWER_CONSISTENCY_ENABLED = True
        s.CONSISTENCY_ROUTES = "relational,comprehensive"
        assert should_enable_consistency("relational") is True
        assert should_enable_consistency("factual") is False


@pytest.mark.asyncio
async def test_answer_review_service_record_creates_gap_and_queue():
    """record_consistency_issue 应同时创建 review 队列与 Gap。"""
    from app.services.answer_review_service import AnswerReviewService

    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    gap_mock = MagicMock()
    gap_mock.id = "gap-1"

    with patch.object(AnswerReviewService, "_canonical_kb_id", AsyncMock(return_value="kb-1")):
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=exec_result)
        with patch("app.services.answer_review_service.GapService") as GCls:
            GCls.return_value.create_gap = AsyncMock(return_value=gap_mock)
            svc = AnswerReviewService(db)
            row = await svc.record_consistency_issue(
                kb_id="kb-1",
                query="测试问题",
                answer_a="答案 A",
                answer_b="答案 B",
                verdict="CONFLICT",
                ctx_hash="abc123",
                reason="test",
                route="relational",
            )
    assert row.kb_id == "kb-1"
    assert row.gap_id == "gap-1"
    assert row.verdict == "CONFLICT"
    GCls.return_value.create_gap.assert_awaited_once()
