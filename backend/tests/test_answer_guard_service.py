"""Post-hoc Answer Guard 单元测试。"""

from app.services.answer_guard_service import (
    REFUSAL_TEXT,
    _parse_verdict,
    is_refusal_answer,
)


def test_parse_verdict_ok():
    assert _parse_verdict("OK") is True
    assert _parse_verdict("ok，通过") is True


def test_parse_verdict_reject():
    assert _parse_verdict("REJECT") is False
    assert _parse_verdict("建议 REJECT") is False


def test_is_refusal_answer():
    assert is_refusal_answer("目前知识库中暂无相关信息") is True
    assert is_refusal_answer("RAG 是检索增强生成") is False


def test_refusal_text_constant():
    assert "暂无相关信息" in REFUSAL_TEXT
