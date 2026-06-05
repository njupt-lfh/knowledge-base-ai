"""对话请求级运行时开关（快速模式等）。

通过 ContextVar 在单次 chat SSE 请求内覆盖 settings，不影响评测脚本与全局 .env。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from .config import settings

_fast_mode: ContextVar[bool] = ContextVar("chat_fast_mode", default=False)

# 快速模式：仅关闭最耗时的链路；保留 SIM-RAG / 图谱 / 多跳以便演示 agent_meta 标签
_FAST_BOOL: dict[str, bool] = {
    "CROSS_ENCODER_RERANK_ENABLED": False,
    "POST_HOC_ANSWER_GUARD_ENABLED": False,
    "ANSWER_CONSISTENCY_ENABLED": False,
}

_FAST_INT: dict[str, int] = {
    "AGENT_MAX_ROUNDS": 1,
}


def is_fast_mode() -> bool:
    return _fast_mode.get()


@contextmanager
def fast_mode_context(enabled: bool) -> Iterator[None]:
    """在 chat_stream 入口包裹，使下游 RAG 读取快速模式覆盖。"""
    token = _fast_mode.set(bool(enabled))
    try:
        yield
    finally:
        _fast_mode.reset(token)


def get_bool(name: str, default: bool = False) -> bool:
    if is_fast_mode() and name in _FAST_BOOL:
        return _FAST_BOOL[name]
    return bool(getattr(settings, name, default))


def get_int(name: str, default: int = 0) -> int:
    if is_fast_mode() and name in _FAST_INT:
        return _FAST_INT[name]
    return int(getattr(settings, name, default))


def get_any(name: str, default: Any = None) -> Any:
    if is_fast_mode() and name in _FAST_BOOL:
        return _FAST_BOOL[name]
    if is_fast_mode() and name in _FAST_INT:
        return _FAST_INT[name]
    return getattr(settings, name, default)
