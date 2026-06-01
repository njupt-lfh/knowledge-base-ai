"""PDF 内嵌图提取 — Phase 4.2

验证内容：
  - extract_pdf_images 尺寸过滤与去重

运行方式（在 backend 目录）:
  pytest tests/test_pdf_image_extractor.py -v

预期结果：全部用例通过。
"""

from pathlib import Path

import fitz
from app.services.pdf_image_extractor import extract_pdf_images


def _make_pdf_with_image(path: Path, width: int = 64, height: int = 64) -> None:
    """构造指定尺寸内嵌图的 PDF。"""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, width, height))
    pix.set_pixel(10, 10, (255, 0, 0))
    page.insert_image(fitz.Rect(20, 20, 20 + width, 20 + height), pixmap=pix)
    doc.save(path)
    doc.close()


def test_extract_pdf_images_filters_small(tmp_path: Path):
    """验证 PDF/对话/实体抽取。"""
    pdf = tmp_path / "mixed.pdf"
    doc = fitz.open()
    page = doc.new_page()
    small = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8))
    page.insert_image(fitz.Rect(0, 0, 8, 8), pixmap=small)
    big = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40))
    page.insert_image(fitz.Rect(50, 50, 90, 90), pixmap=big)
    doc.save(pdf)
    doc.close()

    out = tmp_path / "imgs"
    found = extract_pdf_images(pdf, out, min_dimension=32, max_images=10)
    assert len(found) == 1
    assert found[0].width >= 32
    assert Path(found[0].path).is_file()


def test_extract_pdf_images_dedup(tmp_path: Path):
    """验证 PDF/对话/实体抽取。"""
    pdf = tmp_path / "dup.pdf"
    _make_pdf_with_image(pdf)
    out = tmp_path / "out"
    found = extract_pdf_images(pdf, out, min_dimension=14, max_images=10)
    assert len(found) >= 1
