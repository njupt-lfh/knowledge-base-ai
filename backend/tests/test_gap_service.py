"""GapService 入队判定与分类单元测试。

验证内容：
  - should_enqueue 对拒答话术、低分、正常命中
  - classify_gap 各 gap_type
  - CRAG 充分后跳过 Gap

运行方式（在 backend 目录）:
  pytest tests/test_gap_service.py -v

预期结果：全部用例通过。
"""

from unittest.mock import MagicMock, patch

from app.services.gap_service import GapService


def test_should_enqueue_empty_sources():
    """无检索来源时应入队。"""
    assert GapService.should_enqueue([], "任意回答") is True


def test_should_enqueue_no_info_phrase_chinese():
    """中文拒答话术应触发入队。"""
    sources = [{"chunk_id": "c1", "score": 0.8, "content": "x"}]
    assert GapService.should_enqueue(sources, "目前知识库中暂无相关信息") is True


def test_should_enqueue_no_info_phrase_prompt_wording():
    """Prompt 变体拒答话术也应触发入队。"""
    sources = [{"chunk_id": "c1", "score": 0.8, "content": "x"}]
    assert GapService.should_enqueue(sources, "根据规则，目前知识库中暂无相关内容。") is True


def test_should_enqueue_low_score():
    """低分来源应触发入队。"""
    sources = [{"chunk_id": "c1", "score": 0.1, "content": "x"}]
    assert GapService.should_enqueue(sources, "正常回答") is True


def test_should_not_enqueue_good_hit():
    """高分且正常回答时不应入队。"""
    sources = [{"chunk_id": "c1", "score": 0.8, "content": "x"}]
    assert GapService.should_enqueue(sources, "根据知识库，Python 是高级语言") is False


def test_classify_knowledge_absent():
    """无弱命中时应分类为 KNOWLEDGE_ABSENT。"""
    svc = GapService(db=MagicMock())
    with patch.object(svc, "_probe_weak_hits", return_value=False):
        t = svc.classify_gap("量子纠错", "kb1", [])
    assert t == "KNOWLEDGE_ABSENT"


def test_classify_retrieval_miss_with_weak():
    """有弱命中时应分类为 RETRIEVAL_MISS。"""
    svc = GapService(db=MagicMock())
    with patch.object(svc, "_probe_weak_hits", return_value=True):
        t = svc.classify_gap("RAG 是什么", "kb1", [])
    assert t == "RETRIEVAL_MISS"


def test_classify_user_correction():
    """有 correction_text 时应分类为 USER_CORRECTION。"""
    svc = GapService(db=MagicMock())
    t = svc.classify_gap("q", "kb1", [], correction_text="正确答案是 B")
    assert t == "USER_CORRECTION"


def test_skip_gap_when_crag_sufficient():
    """CRAG 判定充分时 KNOWLEDGE_ABSENT/RETRIEVAL_MISS 应跳过 Gap。"""
    assert GapService.should_skip_gap_after_sufficient_answer(
        crag_sufficient=True,
        crag_refused=False,
        gap_type="KNOWLEDGE_ABSENT",
    )
    assert GapService.should_skip_gap_after_sufficient_answer(
        crag_sufficient=True,
        crag_refused=False,
        gap_type="RETRIEVAL_MISS",
    )


def test_no_skip_gap_when_refused():
    """CRAG 拒答时不应跳过 Gap。"""
    assert not GapService.should_skip_gap_after_sufficient_answer(
        crag_sufficient=False,
        crag_refused=True,
        gap_type="KNOWLEDGE_ABSENT",
    )


def test_no_skip_gap_when_insufficient():
    """CRAG 不充分且未拒答时不应跳过 Gap。"""
    assert not GapService.should_skip_gap_after_sufficient_answer(
        crag_sufficient=False,
        crag_refused=False,
        gap_type="KNOWLEDGE_ABSENT",
    )


def test_no_skip_gap_when_answer_says_no_info():
    """CRAG 充分但 LLM 回答称"暂无相关信息"时不应跳过 Gap。"""
    assert not GapService.should_skip_gap_after_sufficient_answer(
        crag_sufficient=True,
        crag_refused=False,
        gap_type="RETRIEVAL_MISS",
        answer="目前知识库中暂无相关信息，建议补充相关内容。",
    )
    assert not GapService.should_skip_gap_after_sufficient_answer(
        crag_sufficient=True,
        crag_refused=False,
        gap_type="KNOWLEDGE_ABSENT",
        answer="知识库中暂无相关内容。",
    )
