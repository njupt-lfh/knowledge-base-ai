"""PDF 内嵌图片提取 — Phase 4.2"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfEmbeddedImage:
    page_num: int  # 1-based
    image_index: int  # 1-based，页内序号
    path: str
    width: int
    height: int


def extract_pdf_images(
    pdf_path: str | Path,
    out_dir: str | Path,
    *,
    min_dimension: int = 32,
    max_images: int = 30,
) -> list[PdfEmbeddedImage]:
    """从 PDF 提取内嵌图，过滤过小图与重复图，保存为 PNG。"""
    import fitz

    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[PdfEmbeddedImage] = []
    seen_hashes: set[str] = set()

    doc = fitz.open(pdf_path)
    try:
        for page_i in range(len(doc)):
            if len(results) >= max_images:
                break
            page = doc[page_i]
            page_num = page_i + 1
            img_seq = 0
            for img_info in page.get_images(full=True):
                if len(results) >= max_images:
                    break
                xref = img_info[0]
                try:
                    extracted = doc.extract_image(xref)
                except Exception as e:
                    logger.debug("skip xref %s page %s: %s", xref, page_num, e)
                    continue

                w = int(extracted.get("width") or 0)
                h = int(extracted.get("height") or 0)
                if w < min_dimension or h < min_dimension:
                    continue

                img_bytes = extracted["image"]
                digest = hashlib.md5(img_bytes).hexdigest()
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)

                img_seq += 1
                out_path = out_dir / f"p{page_num:03d}_i{img_seq:02d}.png"
                out_path.write_bytes(img_bytes)

                results.append(
                    PdfEmbeddedImage(
                        page_num=page_num,
                        image_index=img_seq,
                        path=str(out_path),
                        width=w,
                        height=h,
                    )
                )
    finally:
        doc.close()

    return results
