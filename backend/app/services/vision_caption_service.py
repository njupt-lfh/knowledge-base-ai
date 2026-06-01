"""图片 Vision 描述服务（Phase 4.1）。

职责：
    调用多模态 LLM 为图片生成中文检索描述，
    供 FTS/图谱索引；向量检索可走 embed_image。

在流水线中的位置：
    image_chunk_ingest_service.ingest_image_chunk_specs → describe_image

依赖服务：
    - LLMService：Vision 补全
    - media_utils.image_to_data_url
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.config import settings

logger = logging.getLogger(__name__)

_CAPTION_SYSTEM = """你是知识库图像理解助手。请用中文简洁描述图片中的关键信息（主体、文字、图表数据、场景），
便于后续检索。不要编造看不见的内容。控制在 200 字以内。"""


async def describe_image(image_path: str, *, filename: str | None = None) -> str:
    """生成图片描述文本；失败时返回降级文案。

    参数:
        image_path: 图片文件路径
        filename: 可选展示文件名

    返回:
        中文描述或降级占位文本
    """
    name = filename or Path(image_path).name
    if settings.LLM_MOCK_MODE:
        import uuid

        tag = uuid.uuid4().hex[:8]
        return f"[图片描述] {name}：Mock 描述 {tag}，含可视化内容与文字信息。"

    from .llm_service import LLMService
    from .media_utils import image_to_data_url

    model = (getattr(settings, "VISION_CAPTION_MODEL", "") or "").strip() or None
    llm = LLMService(model_name=model)

    try:
        data_url = image_to_data_url(image_path)
        raw = await llm.chat_completion(
            [
                {"role": "system", "content": _CAPTION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": f"文件名：{name}。请描述该图片。"},
                    ],
                },
            ],
            temperature=0.2,
            max_tokens=400,
        )
        text = (raw or "").strip()
        if len(text) >= 10:
            return text
    except Exception as e:
        logger.warning("vision caption failed for %s: %s", name, e)

    return f"[图片] {name}：已入库，自动描述暂不可用，请稍后重试或补充手动说明。"
