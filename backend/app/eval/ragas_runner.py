"""RAGAS 评测运行器与 Volcengine 嵌入适配。

提供 `run_ragas_eval` 四指标评测、`VolcengineEmbeddings` 适配层，
以及 API 限额时的单条 LLM 忠实度回退打分。
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Any

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class VolcengineEmbeddings(Embeddings):
    """用项目 EmbeddingService 驱动 RAGAS 所需 embed_query / embed_documents。"""

    def __init__(self) -> None:
        from app.services.embedding_service import EmbeddingService

        self._svc = EmbeddingService()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入文档文本。

        参数:
            texts: 待嵌入字符串列表。

        返回:
            与 texts 等长的向量列表。
        """
        return self._svc.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """嵌入单条查询文本。

        参数:
            text: 查询字符串。

        返回:
            嵌入向量。
        """
        return self._svc.embed_query(text)


def _safe_mean(scores: dict[str, Any]) -> dict[str, float | None]:
    """将 RAGAS 聚合分数字典中的 NaN/Inf 转为 None 并四舍五入。

    参数:
        scores: 原始指标名到数值的映射。

    返回:
        清洗后的指标字典。
    """
    out: dict[str, float | None] = {}
    for k, v in scores.items():
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            out[k] = None
        else:
            try:
                out[k] = round(float(v), 4)
            except (TypeError, ValueError):
                out[k] = None
    return out


def run_ragas_eval(rows: list[dict]) -> dict[str, Any]:
    """对非负样本运行 RAGAS 四指标（faithfulness 等）。

    参数:
        rows: 含 question/answer/contexts/ground_truth/q_type 的评测行。

    返回:
        {"scores": {...}, "errors": [...], "sample_count": n}
    """
    from datasets import Dataset
    from langchain_openai import ChatOpenAI
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    from app.core.config import settings

    errors: list[str] = []
    eval_rows = []
    for r in rows:
        if not r.get("answer") or r.get("q_type") == "negative":
            continue
        ctx = r.get("contexts") or []
        if not ctx:
            errors.append(f"{r.get('id')}: empty contexts, skip ragas")
            continue
        eval_rows.append(
            {
                "question": r["question"],
                "answer": r["answer"],
                "contexts": ctx,
                "ground_truth": r.get("ground_truth") or "",
            }
        )

    if not eval_rows:
        return {"scores": {}, "errors": errors or ["no eligible rows"], "sample_count": 0}

    # RAGAS 内部依赖 OpenAI 环境变量名，此处映射到火山引擎 Key
    os.environ.setdefault("OPENAI_API_KEY", settings.VOLCENGINE_API_KEY)

    llm = ChatOpenAI(
        api_key=settings.VOLCENGINE_API_KEY,
        base_url=settings.VOLCENGINE_BASE_URL,
        model=settings.VOLCENGINE_LLM_MODEL,
        temperature=0,
        max_retries=2,
    )
    embeddings = VolcengineEmbeddings()

    try:
        ds = Dataset.from_list(eval_rows)
        result = evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=llm,
            embeddings=embeddings,
            raise_exceptions=False,
        )
        df = result.to_pandas()
        scores = _safe_mean(df.mean(numeric_only=True).to_dict())
        valid_cols = [c for c in df.columns if df[c].notna().any()]
        if len(valid_cols) < len(df.columns):
            errors.append("partial metric failures (see ragas logs / API quota)")
        return {"scores": scores, "errors": errors, "sample_count": len(eval_rows)}
    except Exception as exc:
        logger.exception("RAGAS evaluate failed")
        return {"scores": {}, "errors": errors + [str(exc)], "sample_count": len(eval_rows)}


async def llm_judge_faithfulness(
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str,
) -> float | None:
    """API 限额时回退：单条忠实度 0–1 打分。

    参数:
        question: 用户问题。
        answer: 待评回答。
        contexts: 参考上下文列表。
        ground_truth: 标准答案（辅助 Judge）。

    返回:
        0.0–1.0 忠实度分数；失败时返回 None。
    """
    import httpx

    from app.core.config import settings

    ctx_text = "\n---\n".join(contexts[:5])[:4000]
    prompt = f"""你是 RAG 评测员。仅根据「参考上下文」判断「回答」是否忠实、无编造。
返回 JSON：{{"score": 0.0 到 1.0 的数字}}

问题：{question}
参考上下文：
{ctx_text}
标准答案（参考）：{ground_truth[:800]}
待评回答：
{answer[:1500]}
"""
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"{settings.VOLCENGINE_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.VOLCENGINE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.VOLCENGINE_LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": 64,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
            data = json.loads(content)
            score = float(data.get("score", 0))
            return max(0.0, min(1.0, score))
    except Exception as exc:
        logger.warning("llm_judge_faithfulness failed: %s", exc)
        return None
