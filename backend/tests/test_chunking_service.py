from app.services.chunking_service import DocumentParser, TextChunker


def test_text_chunker_splits_long_text():
    chunker = TextChunker(chunk_size=50, chunk_overlap=5)
    text = "第一句。" * 30
    chunks = chunker.split(text)
    assert len(chunks) >= 2
    assert all(len(c) > 0 for c in chunks)


def test_text_chunker_preserves_short_text():
    chunker = TextChunker(chunk_size=500, chunk_overlap=50)
    text = "短文本"
    assert chunker.split(text) == ["短文本"]


def test_document_parser_txt(tmp_txt):
    content = DocumentParser.parse(str(tmp_txt), "txt")
    assert "Hello world" in content
    assert "Second line" in content


def test_document_parser_unsupported_type():
    try:
        DocumentParser.parse("x.bin", "bin")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "不支持" in str(e)
