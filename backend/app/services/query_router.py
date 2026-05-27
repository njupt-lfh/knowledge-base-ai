"""Query Router — Phase 2.2 Agentic-lite 问题类型路由（规则优先，无额外 LLM 调用）"""

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
    text = (query or "").strip()
    if not text:
        return "chitchat"

    lower = text.lower()
    if len(text) <= 24 and any(p in lower or p in text for p in _CHITCHAT):
        if "?" not in text and "？" not in text:
            return "chitchat"
        if any(p in text for p in ("你好", "您好", "hello", "hi")):
            return "chitchat"

    if any(re.search(p, text, re.I) for p in _RELATIONAL if ".*" in p):
        return "relational"
    if any(p in text for p in _RELATIONAL if ".*" not in p):
        return "relational"

    if any(p in text for p in _COMPREHENSIVE):
        return "comprehensive"

    return "factual"


def retrieval_top_k_for_route(route: QueryRoute, default: int = 5) -> int:
    if route == "relational":
        return min(10, default + 2)
    if route == "comprehensive":
        return min(10, default + 1)
    if route == "chitchat":
        return 0
    return default


def expand_query_for_retry(query: str, route: QueryRoute) -> str:
    """第二轮检索：关系/综合型问题抽取实体词并放宽匹配。"""
    if route not in ("relational", "comprehensive"):
        return query

    terms = re.findall(r"[\w\u4e00-\u9fff]{2,}", query)
    stop = {"什么", "如何", "怎么", "为什么", "哪些", "之间", "关系", "区别", "对比", "和", "与", "的", "是"}
    key_terms = [t for t in terms if t not in stop][:6]
    if not key_terms:
        return query
    return " ".join(key_terms)
