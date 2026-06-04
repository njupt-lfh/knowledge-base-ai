"""对话快速模式 ContextVar 覆盖。"""

from app.core.chat_runtime import fast_mode_context, get_bool, get_int, is_fast_mode


def test_fast_mode_overrides():
    assert not is_fast_mode()

    with fast_mode_context(True):
        assert is_fast_mode()
        assert get_bool("CROSS_ENCODER_RERANK_ENABLED") is False
        assert get_bool("POST_HOC_ANSWER_GUARD_ENABLED") is False
        assert get_int("AGENT_MAX_ROUNDS") == 1

    assert not is_fast_mode()
