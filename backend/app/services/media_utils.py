"""多模态媒体工具（Phase 4.1）。

职责：
    图片 MIME 推断、扩展名判断、base64 data URL 编码，
    供 EmbeddingService 与 Vision 描述 API 使用。

在流水线中的位置：
    embedding_service.embed_image、vision_caption_service.describe_image

依赖：无
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def is_image_file(path: str | Path) -> bool:
    """判断路径是否为支持的图片扩展名。

    参数:
        path: 文件路径

    返回:
        是否为图片
    """
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def guess_image_mime(path: str | Path) -> str:
    """推断图片 MIME 类型。

    参数:
        path: 文件路径

    返回:
        MIME 字符串，默认 image/jpeg
    """
    ext = Path(path).suffix.lower()
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    if ext in mapping:
        return mapping[ext]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "image/jpeg"


def image_to_data_url(path: str | Path) -> str:
    """读取图片并编码为 data URL（供多模态 API）。

    参数:
        path: 图片路径

    返回:
        data:{mime};base64,{payload} 字符串
    """
    p = Path(path)
    raw = p.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    mime = guess_image_mime(p)
    return f"data:{mime};base64,{b64}"
