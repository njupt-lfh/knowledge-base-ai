from unittest.mock import MagicMock, patch

import pytest

from app.services.gap_service import GapService


def test_should_enqueue_empty_sources():
    assert GapService.should_enqueue([], "任意回答") is True


def test_should_enqueue_no_info_phrase_chinese():
    sources = [{"chunk_id": "c1", "score": 0.8, "content": "x"}]
    assert GapService.should_enqueue(sources, "目前知识库中暂无相关信息") is True


def test_should_enqueue_no_info_phrase_prompt_wording():
    sources = [{"chunk_id": "c1", "score": 0.8, "content": "x"}]
    assert GapService.should_enqueue(sources, "根据规则，目前知识库中暂无相关内容。") is True


def test_should_enqueue_low_score():
    sources = [{"chunk_id": "c1", "score": 0.1, "content": "x"}]
    assert GapService.should_enqueue(sources, "正常回答") is True


def test_should_not_enqueue_good_hit():
    sources = [{"chunk_id": "c1", "score": 0.8, "content": "x"}]
    assert GapService.should_enqueue(sources, "根据知识库，Python 是高级语言") is False


def test_classify_knowledge_absent():
    svc = GapService(db=MagicMock())
    with patch.object(svc, "_probe_weak_hits", return_value=False):
        t = svc.classify_gap("量子纠错", "kb1", [])
    assert t == "KNOWLEDGE_ABSENT"


def test_classify_retrieval_miss_with_weak():
    svc = GapService(db=MagicMock())
    with patch.object(svc, "_probe_weak_hits", return_value=True):
        t = svc.classify_gap("RAG 是什么", "kb1", [])
    assert t == "RETRIEVAL_MISS"


def test_classify_user_correction():
    svc = GapService(db=MagicMock())
    t = svc.classify_gap("q", "kb1", [], correction_text="正确答案是 B")
    assert t == "USER_CORRECTION"
