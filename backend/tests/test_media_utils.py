"""media_utils 单元测试 — Phase 4.1"""

from pathlib import Path

from app.services.media_utils import (
    IMAGE_EXTENSIONS,
    guess_image_mime,
    image_to_data_url,
    is_image_file,
)


def test_is_image_file():
    assert is_image_file("a.PNG")
    assert not is_image_file("doc.pdf")
    assert ".webp" in IMAGE_EXTENSIONS


def test_guess_image_mime_and_data_url(tmp_path: Path):
    p = tmp_path / "x.jpg"
    p.write_bytes(b"\xff\xd8\xff")
    assert guess_image_mime(p) == "image/jpeg"
    url = image_to_data_url(p)
    assert url.startswith("data:image/jpeg;base64,")
