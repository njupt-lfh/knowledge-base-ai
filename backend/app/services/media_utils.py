"""多模态媒体工具 — Phase 4.1"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def is_image_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def guess_image_mime(path: str | Path) -> str:
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
    p = Path(path)
    raw = p.read_bytes()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    mime = guess_image_mime(p)
    return f"data:{mime};base64,{b64}"
