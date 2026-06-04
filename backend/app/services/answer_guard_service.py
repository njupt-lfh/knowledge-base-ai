"""生成后 grounded 自检（Week 0 Post-hoc Answer Guard）。

职责：
    在 LLM 生成回答后，用轻量 Prompt 检查回答是否严格基于 context；
    若含未经证实的信息则返回拒答话术。

在流水线中的位置：
    AgentOrchestrator.generate_stream → verify_answer_grounded

依赖服务：
    - LLMService.chat_completion（非流式，低 max_tokens）
"""

from __future__ import annotations

from ..core.config import settings

REFUSAL_TEXT = "目前知识库中暂无相关信息，已为您记录到知识缺口队列，请稍后补充资料或联系管理员。"

_POST_HOC_SYSTEM = """你是 RAG 回答质检员。仅根据「知识库内容」判断「助手回答」是否严格有据。

规则：
1. 若回答中的事实、结论均可从知识库内容中找到依据，回复 exactly: OK
2. 若回答包含猜测、推理延伸、或知识库未提及的信息，回复 exactly: REJECT
3. 只输出 OK 或 REJECT，不要解释"""


def _build_check_messages(query: str, context: str, answer: str) -> list[dict]:
    """构造 Post-hoc 自检消息。"""
    user = (
        f"用户问题：{query}\n\n"
        f"知识库内容：\n{context[:3500]}\n\n"
        f"助手回答：\n{answer[:2000]}\n\n"
        "上述回答是否严格基于知识库内容？"
    )
    return [{"role": "system", "content": _POST_HOC_SYSTEM}, {"role": "user", "content": user}]


def _parse_verdict(raw: str) -> bool:
    """解析 LLM  verdict，True 表示通过。"""
    text = (raw or "").strip().upper()
    if "REJECT" in text:
        return False
    if "OK" in text or text in ("通过", "是", "YES"):
        return True
    # 保守：无法解析时视为不通过
    return False


def is_refusal_answer(answer: str) -> bool:
    """是否已是拒答话术（跳过 Post-hoc）。"""
    a = (answer or "").strip()
    if not a:
        return True
    return "暂无相关信息" in a or a.startswith("目前知识库")


async def verify_answer_grounded(
    query: str,
    context: str,
    answer: str,
    *,
    llm=None,
) -> tuple[bool, str]:
    """Post-hoc 检查回答是否 grounded。

    返回:
        (passed, final_answer) — 未通过时 final_answer 为拒答话术
    """
    from ..core import chat_runtime as rt

    if not rt.get_bool("POST_HOC_ANSWER_GUARD_ENABLED", True):
        return True, answer

    if is_refusal_answer(answer):
        return True, answer

    if not (context or "").strip() or context.strip() == "知识库中暂无相关内容":
        return False, REFUSAL_TEXT

    from .llm_service import LLMService

    client = llm or LLMService()
    if client.mock_mode:
        # Mock 模式下跳过额外 LLM 调用
        return True, answer

    try:
        raw = await client.chat_completion(
            _build_check_messages(query, context, answer),
            temperature=0.0,
            max_tokens=16,
        )
        if _parse_verdict(raw):
            return True, answer
    except Exception:
        # 质检失败时不阻断主流程
        return True, answer

    return False, REFUSAL_TEXT
