"""media_utils 单元测试 — Phase 4.1

验证内容：
  - 图片扩展名、MIME 与 data URL

运行方式（在 backend 目录）:
  pytest tests/test_media_utils.py -v

预期结果：全部用例通过。
"""

from pathlib import Path

from app.services.media_utils import (
    IMAGE_EXTENSIONS,
    guess_image_mime,
    image_to_data_url,
    is_image_file,
)


def test_is_image_file():
    """验证图片文件扩展名判断。"""
    assert is_image_file("a.PNG")
    assert not is_image_file("doc.pdf")
    assert ".webp" in IMAGE_EXTENSIONS


def test_guess_image_mime_and_data_url(tmp_path: Path):
    """验证 MIME 与 data URL。"""
    p = tmp_path / "x.jpg"
    p.write_bytes(b"\xff\xd8\xff")
    assert guess_image_mime(p) == "image/jpeg"
    url = image_to_data_url(p)
    assert url.startswith("data:image/jpeg;base64,")
