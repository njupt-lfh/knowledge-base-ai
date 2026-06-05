"""对话快速模式 ContextVar 覆盖。"""

from app.core.chat_runtime import fast_mode_context, get_bool, get_int, is_fast_mode


def test_fast_mode_overrides():
    assert not is_fast_mode()

    with fast_mode_context(True):
        assert is_fast_mode()
        assert get_bool("CROSS_ENCODER_RERANK_ENABLED") is False
        assert get_bool("POST_HOC_ANSWER_GUARD_ENABLED") is False
        assert get_bool("ANSWER_CONSISTENCY_ENABLED") is False
        assert get_int("AGENT_MAX_ROUNDS") == 1
        # 演示用：SIM-RAG / 图谱 / 多跳仍走 .env 默认（通常为 true）
        assert get_bool("SIM_RAG_ENABLED", True) is True
        assert get_bool("GRAPH_ENABLED", True) is True

    assert not is_fast_mode()
