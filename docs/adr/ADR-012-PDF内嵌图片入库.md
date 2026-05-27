# ADR-012：PDF 内嵌图片入库（Phase 4.2）

## 状态

已接受（2026-05-24）

## 背景

Phase 4.1 支持独立图片上传；PDF 仍仅用 pypdf 抽文本，内嵌图（图表、截图）无法检索。

## 决策

1. **提取**：PyMuPDF (`fitz`) 遍历每页 `get_images` → `extract_image`，保存 PNG；过滤宽/高 `< PDF_IMAGE_MIN_DIMENSION`（默认 32）；MD5 去重；上限 `PDF_IMAGE_MAX_PER_DOCUMENT`（默认 30）。
2. **入库**：复用 `image_chunk_ingest_service`：Vision caption + `embed_image` + FTS/图谱；chunk 前缀 `[PDF图片] {文件名} 第{n}页 图{i}`；Chroma `media_type=pdf_image`。
3. **管线**：`_process_document` 先文本块（`media_type=text`），再 PDF 图块；允许「仅图片无文本」的 PDF 完成入库。
4. **开关**：`PDF_IMAGE_EXTRACTION_ENABLED`（默认 true）。

## 依赖

- `pymupdf==1.25.5`（requirements.txt）

## 验证

```bash
cd backend
pip install pymupdf==1.25.5
python -m pytest tests/test_pdf_image_extractor.py tests/test_phase4_pdf_images.py -q --no-cov
python scripts/verify_phase4_2.py
```

## 后果

- 含大量装饰性小图的 PDF 可能触达上限或产生较多 Vision 调用；可调 `PDF_IMAGE_MIN_DIMENSION` / `PDF_IMAGE_MAX_PER_DOCUMENT`。
- 提取图缓存于 `{UPLOAD_DIR}/{doc_id}_pdfimg/`。
