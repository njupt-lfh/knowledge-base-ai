"""Chunk 级实体关系抽取 — Phase 3（LLM / Mock 规则）"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..core.config import settings

logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = """你是知识图谱抽取助手。从给定文本中抽取最多 {max_n} 组实体关系三元组。
只输出 JSON，格式：{{"triples": [{{"subject": "主体", "predicate": "关系", "object": "客体"}}]}}
要求：主体/客体为简短名词或短语；关系为动词或关系词；不要编造文本中不存在的事实。"""


def _normalize_entity(name: str) -> str:
    return re.sub(r"\s+", "", name.strip())[:128]


def _mock_extract_triples(content: str, max_n: int) -> list[dict[str, str]]:
    triples: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(subject: str, predicate: str, obj: str) -> None:
        s, p, o = _normalize_entity(subject), _normalize_entity(predicate), _normalize_entity(obj)
        if len(s) < 2 or len(o) < 2 or s == o:
            return
        key = (s, p, o)
        if key in seen:
            return
        seen.add(key)
        triples.append({"subject": s, "predicate": p, "object": o})

    for m in re.finditer(r"([^\s，。；、]{2,12})[与和及]([^\s，。；、]{2,12})", content):
        _add(m.group(1), "关联", m.group(2))
    for m in re.finditer(r"([^\s，。；、]{2,12})是([^\s，。；、]{2,24})", content):
        _add(m.group(1), "是", m.group(2))
    for m in re.finditer(r"([^\s，。；、]{2,12})(?:属于|包含于)([^\s，。；、]{2,24})", content):
        _add(m.group(1), "属于", m.group(2))
    for m in re.finditer(
        r"([^\s，。；、]{2,12})(?:对比|区别|不同于)([^\s，。；、]{2,12})", content
    ):
        _add(m.group(1), "对比", m.group(2))

    return triples[:max_n]


async def extract_triples_from_chunk(content: str) -> list[dict[str, Any]]:
    """从 chunk 文本抽取三元组列表。"""
    max_n = getattr(settings, "GRAPH_MAX_TRIPLES_PER_CHUNK", 5)
    if settings.LLM_MOCK_MODE:
        return _mock_extract_triples(content, max_n)

    from .llm_service import LLMService

    model_name = (getattr(settings, "GRAPH_EXTRACTION_MODEL", "") or "").strip() or None
    llm = LLMService(model_name=model_name)
    prompt = _EXTRACT_SYSTEM.format(max_n=max_n)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content[:2000]},
    ]

    raw = ""
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            raw = await llm.chat_completion(messages, temperature=0.1, max_tokens=512)
            break
        except Exception as e:
            last_err = e
            logger.warning("entity extract LLM attempt %s failed: %s", attempt + 1, e)
            if attempt < 2:
                import asyncio

                await asyncio.sleep(1.5 * (attempt + 1))
    if not raw and last_err:
        logger.warning("entity extract fallback to rules after LLM errors: %s", last_err)
        return _mock_extract_triples(content, max_n)
    try:
        data = json.loads(raw)
        rows = data.get("triples") or []
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            logger.warning("entity extract JSON parse failed")
            return _mock_extract_triples(content, max_n)
        try:
            rows = json.loads(m.group(0)).get("triples") or []
        except json.JSONDecodeError:
            return _mock_extract_triples(content, max_n)

    out: list[dict[str, Any]] = []
    for row in rows[:max_n]:
        s = _normalize_entity(str(row.get("subject", "")))
        p = _normalize_entity(str(row.get("predicate", "关联"))) or "关联"
        o = _normalize_entity(str(row.get("object", "")))
        if len(s) >= 2 and len(o) >= 2 and s != o:
            out.append({"subject": s, "predicate": p[:64], "object": o, "confidence": 0.85})
    return out or _mock_extract_triples(content, max_n)
