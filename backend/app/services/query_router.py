"""Query Router 问题类型路由（Phase 2.2 Agentic-lite，规则优先，无 LLM）。

职责：
    根据关键词与句式将用户问题分类为 factual / relational / comprehensive / chitchat，
    影响检索 top_k、CRAG 阈值、图谱启用与 SIM-RAG 策略。

在流水线中的位置：
    AgentOrchestrator.run → route_query
    sim_rag_service.should_use_sim_rag

依赖：无（纯规则模块，被 CRAG / Agent / SIM-RAG 消费）
"""

from __future__ import annotations

import re
from typing import Literal

QueryRoute = Literal["factual", "relational", "comprehensive", "chitchat"]

_CHITCHAT = (
    "你好",
    "您好",
    "hello",
    "hi",
    "hey",
    "谢谢",
    "感谢",
    "多谢",
    "再见",
    "拜拜",
    "早上好",
    "下午好",
    "晚上好",
    "在吗",
    "你是谁",
    "你能做什么",
)

_RELATIONAL = (
    "关系",
    "区别",
    "差异",
    "对比",
    "比较",
    "不同",
    "相同",
    "相似",
    "联系",
    " versus ",
    " vs ",
    "和.*的",
    "与.*的",
)

_COMPREHENSIVE = (
    "总结",
    "综述",
    "概述",
    "归纳",
    "有哪些",
    "包括哪些",
    "列举",
    "全面",
    "整体",
    "分别是什么",
)


def route_query(query: str) -> QueryRoute:
    """规则路由：判定问题类型。

    参数:
        query: 用户问题

    返回:
        QueryRoute 枚举值之一
    """
    text = (query or "").strip()
    if not text:
        return "chitchat"

    lower = text.lower()
    if len(text) <= 24 and any(p in lower or p in text for p in _CHITCHAT):
        if "?" not in text and "？" not in text:
            return "chitchat"
        if any(p in text for p in ("你好", "您好", "hello", "hi")):
            return "chitchat"

    # 关系/对比类 → 倾向启用图谱检索
    if any(re.search(p, text, re.I) for p in _RELATIONAL if ".*" in p):
        return "relational"
    if any(p in text for p in _RELATIONAL if ".*" not in p):
        return "relational"

    if any(p in text for p in _COMPREHENSIVE):
        return "comprehensive"

    return "factual"


def retrieval_top_k_for_route(route: QueryRoute, default: int = 5) -> int:
    """按路由类型调整检索条数。

    参数:
        route: 问题类型
        default: 默认 top_k

    返回:
        调整后的 top_k（chitchat 为 0）
    """
    if route == "relational":
        return min(10, default + 2)
    if route == "comprehensive":
        return min(10, default + 1)
    if route == "chitchat":
        return 0
    return default


def expand_query_for_retry(query: str, route: QueryRoute) -> str:
    """第二轮检索：关系/综合型问题抽取实体词并放宽匹配。

    参数:
        query: 原始查询
        route: 问题类型

    返回:
        扩展/简化后的检索 query
    """
    if route not in ("relational", "comprehensive"):
        return query

    terms = re.findall(r"[\w\u4e00-\u9fff]{2,}", query)
    stop = {
        "什么",
        "如何",
        "怎么",
        "为什么",
        "哪些",
        "之间",
        "关系",
        "区别",
        "对比",
        "和",
        "与",
        "的",
        "是",
    }
    key_terms = [t for t in terms if t not in stop][:6]
    if not key_terms:
        return query
    return " ".join(key_terms)
