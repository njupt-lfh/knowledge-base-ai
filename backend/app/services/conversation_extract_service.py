"""对话知识提炼 — Phase 1.5 结构化抽取"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..services.llm_service import LLMService

logger = logging.getLogger(__name__)

AUTO_INGEST_GAP_TYPES = ("USER_PROVIDED", "USER_CORRECTION")


class ConversationExtractService:
    def __init__(self):
        self.llm = LLMService()

    async def extract_from_turn(
        self,
        user_message: str,
        assistant_message: str,
        *,
        hint_gap_type: str | None = None,
    ) -> dict[str, Any] | None:
        """结构化提炼；无 source_ref 时返回 None（拒绝编造）。"""
        if self.llm.mock_mode:
            if hint_gap_type in AUTO_INGEST_GAP_TYPES and len(user_message.strip()) >= 8:
                return {
                    "has_knowledge": True,
                    "gap_type": hint_gap_type,
                    "title": user_message[:40],
                    "content": user_message,
                    "tags": [],
                    "entities": [],
                    "source_ref": user_message[:200],
                }
            return None

        hint = f"优先 gap_type={hint_gap_type}。" if hint_gap_type else ""
        prompt = (
            "分析以下对话，判断是否包含用户明确提供、可入库的事实或纠正。\n"
            f"{hint}\n"
            "规则：\n"
            "- gap_type 只能是 USER_PROVIDED（用户陈述新事实）或 USER_CORRECTION（用户纠正助手）\n"
            "- source_ref 必须为用户原话的直接引用（verbatim），无引用则 has_knowledge=false\n"
            "- 不要编造对话中未出现的知识\n"
            "- KNOWLEDGE_ABSENT 场景不要生成 content\n\n"
            "仅返回 JSON：\n"
            '{"has_knowledge":bool,"gap_type":"USER_PROVIDED|USER_CORRECTION",'
            '"title":"str","content":"str","tags":[],"entities":[],"source_ref":"str"}\n\n'
            f"用户：{user_message}\n助手：{assistant_message}"
        )
        try:
            raw = await self.llm.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800,
            )
            data = self._parse_json(raw)
            if not data or not data.get("has_knowledge"):
                return None
            gap_type = data.get("gap_type") or hint_gap_type
            if gap_type not in AUTO_INGEST_GAP_TYPES:
                return None
            source_ref = (data.get("source_ref") or "").strip()
            if not source_ref or not self._source_in_dialog(source_ref, user_message, assistant_message):
                logger.info("extract: rejected — missing or invalid source_ref")
                return None
            data["gap_type"] = gap_type
            data["source_ref"] = source_ref
            return data
        except Exception as e:
            logger.warning("extract_from_turn failed: %s", e)
            return None

    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        return json.loads(text[start:end])

    @staticmethod
    def _source_in_dialog(source_ref: str, user_message: str, assistant_message: str) -> bool:
        ref = source_ref.strip()
        if len(ref) < 4:
            return False
        if ref in user_message or ref in assistant_message:
            return True
        # 允许较短引用的子串匹配
        if len(ref) >= 8 and (ref[:12] in user_message or ref[:12] in assistant_message):
            return True
        return False

    @staticmethod
    def pack_suggested(data: dict[str, Any]) -> str:
        return json.dumps(
            {
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "tags": data.get("tags") or [],
                "entities": data.get("entities") or [],
                "gap_type": data.get("gap_type"),
            },
            ensure_ascii=False,
        )
