"""TextChunker 与 DocumentParser 单元测试。

验证内容：
  - 长文本分块、短文本保留
  - txt 解析与不支持类型抛错

运行方式（在 backend 目录）:
  pytest tests/test_chunking_service.py -v

预期结果：全部用例通过。
"""

import pytest
from app.services.chunking_service import DocumentParser, TextChunker


def test_text_chunker_splits_long_text():
    """长文本应被切分为多个非空 chunk。"""
    chunker = TextChunker(chunk_size=50, chunk_overlap=5)
    text = "第一句。" * 30
    chunks = chunker.split(text)
    assert len(chunks) >= 2
    assert all(len(c) > 0 for c in chunks)


def test_text_chunker_preserves_short_text():
    """短于 chunk_size 的文本应保持原样不分块。"""
    chunker = TextChunker(chunk_size=500, chunk_overlap=50)
    text = "短文本"
    assert chunker.split(text) == ["短文本"]


def test_document_parser_txt(tmp_txt):
    """txt 文件应正确解析为包含两行内容的字符串。"""
    content = DocumentParser.parse(str(tmp_txt), "txt")
    assert "Hello world" in content
    assert "Second line" in content


def test_document_parser_unsupported_type():
    """不支持的文件类型应抛出 ValueError。"""
    with pytest.raises(ValueError, match="不支持"):
        DocumentParser.parse("x.bin", "bin")
