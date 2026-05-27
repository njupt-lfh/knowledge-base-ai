"""对话历史压缩 — Phase 2.3 summary memory（无额外 LLM 调用）"""

from __future__ import annotations

from ..core.config import settings


def compress_history(
    history: list[dict],
    *,
    recent_turns: int | None = None,
    max_summary_chars: int | None = None,
) -> list[dict]:
    """
    保留最近 N 轮完整对话，更早轮次压缩为一条摘要 system 消息。
    返回可直接拼入 LLM messages 的列表。
    """
    if not history:
        return []

    turns = recent_turns if recent_turns is not None else getattr(settings, "HISTORY_RECENT_TURNS", 2)
    summary_cap = max_summary_chars if max_summary_chars is not None else getattr(
        settings, "HISTORY_SUMMARY_MAX_CHARS", 600
    )
    keep = max(2, turns * 2)

    if len(history) <= keep:
        return list(history)

    older = history[:-keep]
    recent = history[-keep:]

    lines: list[str] = []
    per_line = 50 if len(older) > 8 else 80
    for msg in older:
        role_label = "用户" if msg.get("role") == "user" else "助手"
        snippet = (msg.get("content") or "").replace("\n", " ").strip()[:per_line]
        if snippet:
            lines.append(f"{role_label}: {snippet}")

    if not lines:
        return list(recent)

    summary = "此前对话摘要：\n" + "\n".join(lines)
    if len(summary) > summary_cap:
        summary = summary[:summary_cap] + "…"

    return [{"role": "system", "content": summary}, *recent]


def estimate_messages_chars(messages: list[dict]) -> int:
    return sum(len(m.get("content") or "") for m in messages)


def history_compression_ratio(full: list[dict], compressed: list[dict]) -> float:
    """相对完整历史的字符节省比例。"""
    if len(full) <= 4:
        return 0.0
    full_len = estimate_messages_chars(full)
    if full_len <= 0:
        return 0.0
    comp_len = estimate_messages_chars(compressed)
    saved = max(0, full_len - comp_len)
    return round(saved / full_len, 4)
