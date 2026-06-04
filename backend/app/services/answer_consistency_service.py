"""答案一致性守卫（Phase 2）。

双路径生成 + 交叉验证：
  Path-A 严格检索 → 答案A | Path-B 扩展检索 → 答案B
  → LLM 判定一致性 → OK输出 / CONFLICT拒答+入review队列

参考：IDEAL-RAG (2025), CRUISE (KDD Cup 2025)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from ..core.config import settings

logger = logging.getLogger(__name__)

# 一致性判定 Prompt
CONSISTENCY_PROMPT = """你是一个答案一致性检查器。请判断以下两个答案是否一致。

问题：{query}

答案A（基于严格检索）：{answer_a}

答案B（基于扩展检索）：{answer_b}

判断规则：
1. 如果两个答案的核心结论一致，回复 "OK"。
2. 如果两个答案存在事实性矛盾（如数值不同、结论相反、一个说有另一个说没有），回复 "CONFLICT"。
3. 如果无法判断（如一个答案太短、两个答案讨论不同方面），回复 "UNCERTAIN"。

只回复一个词：OK / CONFLICT / UNCERTAIN"""


@dataclass
class ConsistencyResult:
    """一致性检查结果。"""

    verdict: str  # OK | CONFLICT | UNCERTAIN
    answer_a: str = ""
    answer_b: str = ""
    answer_param: str = ""  # Path-C 参数知识答案（可选）
    reason: str = ""
    ctx_hash: str = ""  # context 哈希，用于去重审计


async def check_consistency(
    query: str,
    answer_a: str,
    answer_b: str,
    *,
    answer_param: str = "",
) -> ConsistencyResult:
    """LLM 判定两个答案是否一致。

    参数:
        query: 用户问题
        answer_a: 路径A（严格检索）的答案
        answer_b: 路径B（扩展检索）的答案
        answer_param: 可选路径C（参数知识）答案

    返回:
        ConsistencyResult
    """
    # 快捷路径：任一答案为空 → UNCERTAIN
    if not answer_a.strip() or not answer_b.strip():
        return ConsistencyResult(
            verdict="UNCERTAIN",
            answer_a=answer_a,
            answer_b=answer_b,
            answer_param=answer_param,
            reason="one or both answers empty",
        )

    # 快捷路径：答案完全相同（去除空白后）→ OK
    if answer_a.strip() == answer_b.strip():
        return ConsistencyResult(
            verdict="OK",
            answer_a=answer_a,
            answer_b=answer_b,
            answer_param=answer_param,
            reason="identical answers",
        )

    # 路径C：参数知识检查（可选）
    if answer_param.strip():
        param_conflict = _quick_param_conflict(query, answer_a, answer_param)
        if param_conflict:
            return ConsistencyResult(
                verdict="CONFLICT",
                answer_a=answer_a,
                answer_b=answer_b,
                answer_param=answer_param,
                reason="param knowledge contradicts context answer",
            )

    # LLM 判定
    prompt = CONSISTENCY_PROMPT.format(
        query=query,
        answer_a=answer_a[:1500],
        answer_b=answer_b[:1500],
    )

    try:
        from .llm_service import LLMService

        llm = LLMService()
        response = await llm.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        verdict_text = (response or "").strip().upper()

        if "CONFLICT" in verdict_text:
            verdict = "CONFLICT"
        elif "UNCERTAIN" in verdict_text:
            verdict = "UNCERTAIN"
        else:
            verdict = "OK"

        ctx_hash = hashlib.md5((answer_a[:200] + answer_b[:200]).encode()).hexdigest()[:12]

        return ConsistencyResult(
            verdict=verdict,
            answer_a=answer_a,
            answer_b=answer_b,
            answer_param=answer_param,
            reason=f"LLM judge: {verdict_text[:100]}",
            ctx_hash=ctx_hash,
        )
    except Exception as e:
        logger.warning("consistency check failed: %s", e)
        # 判定失败 → 默认放行（不阻塞用户）
        return ConsistencyResult(
            verdict="OK",
            answer_a=answer_a,
            answer_b=answer_b,
            answer_param=answer_param,
            reason=f"judge error, default pass: {e}",
        )


def _quick_param_conflict(query: str, context_answer: str, param_answer: str) -> bool:
    """快速参数知识冲突检测（启发式）。

    如果参数答案声称"知道"但上下文答案说"暂无相关信息"→ 不是冲突
    如果两个答案都给出了事实性陈述但核心词不重叠 → 潜在冲突

    返回 True 表示疑似冲突。
    """
    # 上下文答案拒答 → 不冲突（参数知识可能正确，但库内无信息）
    no_info = ("暂无相关信息", "暂无相关内容", "知识库中暂无", "no relevant information")
    if any(p in context_answer for p in no_info):
        return False

    # 参数答案说不知道 → 不冲突
    if any(p in param_answer for p in no_info):
        return False

    # 简单启发：提取两个答案中的中文核心词，重叠率 < 0.3 → 潜在冲突
    ctx_chars = set(c for c in context_answer if "一" <= c <= "鿿")
    param_chars = set(c for c in param_answer if "一" <= c <= "鿿")
    if not ctx_chars or not param_chars:
        return False

    overlap = len(ctx_chars & param_chars) / max(len(ctx_chars), len(param_chars))
    return overlap < 0.15  # 极低重叠 → 疑似讨论完全不同的话题


async def generate_dual_answers(
    query: str,
    context_a: str,
    context_b: str,
    *,
    system_prompt_template: str,
    generate_fn,
) -> tuple[str, str]:
    """并行生成两个答案。

    参数:
        query: 用户问题
        context_a: 路径A的上下文
        context_b: 路径B的上下文
        system_prompt_template: 系统提示模板（含 {context} 占位符）
        generate_fn: async (messages) -> str 生成函数

    返回:
        (answer_a, answer_b)
    """
    prompt_a = system_prompt_template.replace("{context}", context_a)
    prompt_b = system_prompt_template.replace("{context}", context_b)

    messages_a = [
        {"role": "system", "content": prompt_a},
        {"role": "user", "content": query},
    ]
    messages_b = [
        {"role": "system", "content": prompt_b},
        {"role": "user", "content": query},
    ]

    # 并行生成
    results = await asyncio.gather(
        generate_fn(messages_a),
        generate_fn(messages_b),
        return_exceptions=True,
    )

    answer_a = _safe_result(results[0])
    answer_b = _safe_result(results[1])

    return answer_a, answer_b


async def generate_param_answer(query: str, generate_fn) -> str:
    """生成无上下文的参数知识答案（Path-C 可选）。

    参数:
        query: 用户问题
        generate_fn: async (messages) -> str 生成函数

    返回:
        参数知识答案
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个通用知识助手。请根据你的知识简要回答问题。"
                "如果不知道或不确定，请回复'不知道'。"
                "回答请控制在100字以内。"
            ),
        },
        {"role": "user", "content": query},
    ]
    try:
        result = await generate_fn(messages)
        return _safe_result(result)
    except Exception:
        return ""


def _safe_result(result: Any) -> str:
    """安全提取生成结果。"""
    if isinstance(result, Exception):
        logger.warning("dual-gen failed: %s", result)
        return ""
    if result is None:
        return ""
    return str(result)


def should_enable_consistency(route: str) -> bool:
    """根据路由类型判断是否启用双路径一致性检查。

    参数:
        route: QueryRoute 值

    返回:
        True 表示启用
    """
    from ..core import chat_runtime as rt

    if not rt.get_bool("ANSWER_CONSISTENCY_ENABLED", True):
        return False
    enabled_routes = getattr(settings, "CONSISTENCY_ROUTES", "relational,comprehensive")
    return route in enabled_routes.split(",")
