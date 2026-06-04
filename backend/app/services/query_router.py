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
    "关联",
    "两段",
    "多跳",
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

    # 综合 + 关联/两段 → 多跳（评测 v2 multi_hop 自然问法）
    if "综合" in text and any(k in text for k in ("关联", "两段", "之间", "关系")):
        return "relational"

    if any(p in text for p in _COMPREHENSIVE):
        return "comprehensive"

    return "factual"


def retrieval_top_k_for_route(
    route: QueryRoute,
    default: int = 5,
    *,
    query: str = "",
) -> int:
    """按路由类型 + 查询长度调整检索条数。

    参数:
        route: 问题类型
        default: 默认 top_k
        query: 原始查询文本，用于动态调整

    返回:
        调整后的 top_k（chitchat 为 0）
    """
    if route == "chitchat":
        return 0
    # 基础 top_k
    if route == "factual":
        k = min(5, default)
    elif route == "comprehensive":
        k = min(4, default)
    elif route == "relational":
        k = min(5, default)
    else:
        k = default
    # 动态调整：短查询可能需要更多候选（embedding 语义弱），长查询也可能需要
    if query:
        n = len(query.strip())
        if n < 15:
            k = max(k, 4)
        elif n > 80:
            k = min(k + 1, 10)
    return k


def decompose_multi_hop_query(query: str) -> list[str]:
    """G-L1：规则化多跳查询分解。

    从多跳问法中抽取 anchor 实体词，用于图谱种子与子查询。

    参数:
        query: 用户查询

    返回:
        分解出的子查询/实体列表（可能为空）
    """
    import re

    seeds: list[str] = []
    # 模式0：v2 kg 模板「A」和「B」之间有什么联系（通过…）
    m = re.search(
        r"「([^」]+)」\s*[与和]\s*「([^」]+)」\s*之间有什么联系",
        query,
    )
    if m:
        a, b = m.group(1).strip(), m.group(2).strip()
        if len(a) >= 2:
            seeds.append(a)
        if len(b) >= 2:
            seeds.append(b)
        return seeds

    # 模式1：「A 与 B 的关系/区别/对比」
    m = re.search(
        r"「?([^」与和、,，]+)」?\s*[与和、]\s*「?([^」与和、,，]+)」?\s*(?:的)?(?:关系|区别|对比|关联|异同)",
        query,
    )
    if m:
        a, b = m.group(1).strip(), m.group(2).strip()
        if len(a) >= 2:
            seeds.append(a)
        if len(b) >= 2:
            seeds.append(b)
        return seeds

    # 模式2：「综合两段…「A」与「B」有何关联」（v2 multi_hop 非 kg 模板）
    m = re.search(
        r"综合.*?[「『](.+?)[」』]\s*[与和]\s*[「『](.+?)[」』]\s*有何关联",
        query,
    )
    if m:
        a, b = m.group(1).strip(), m.group(2).strip()
        if len(a) >= 2:
            seeds.append(a)
        if len(b) >= 2:
            seeds.append(b)
        return seeds

    # 模式3：「涉及哪些/包含哪些」（comprehensive）
    cjk = re.findall(r"[一-鿿]{2,}", query)
    stop = {
        "综合",
        "知识库",
        "内容",
        "说明",
        "有何",
        "关联",
        "两段",
        "之间",
        "关系",
        "有什么区别",
        "有什么",
        "是什么",
        "如何",
        "怎么",
        "哪些",
        "涉及",
        "包含",
    }
    for w in cjk:
        if w not in stop and len(w) >= 2:
            seeds.append(w)
    return seeds[:5]  # 最多 5 个种子


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
