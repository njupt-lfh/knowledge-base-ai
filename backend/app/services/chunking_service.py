"""文档解析与分块服务。

职责：
    将 PDF/Markdown/TXT 解析为纯文本，再按 chunk_size/overlap 或结构边界分块，
    为入库流水线提供文本片段。

在流水线中的位置：
    document_service._process_document / ingest_manual → DocumentParser + TextChunker

依赖：无（pypdf、markdown 库）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import markdown
from pypdf import PdfReader


class DocumentParser:
    """文件解析器 — 支持 PDF / Markdown / TXT。"""

    @staticmethod
    def parse(file_path: str, file_type: str) -> str:
        """按文件类型解析为纯文本。

        参数:
            file_path: 文件路径
            file_type: pdf | md | txt

        返回:
            提取的全文

        Raises:
            ValueError: 不支持的文件类型
        """
        if file_type == "pdf":
            return DocumentParser._parse_pdf(file_path)
        elif file_type == "md":
            return DocumentParser._parse_markdown(file_path)
        elif file_type == "txt":
            return DocumentParser._parse_txt(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")

    @staticmethod
    def read_markdown_raw(path: str) -> str:
        """读取 Markdown 原文（保留标题结构）。"""
        with open(path, encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def parse_pdf_pages(path: str) -> list[str]:
        """PDF 逐页提取文本。"""
        reader = PdfReader(path)
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                pages.append(page_text.strip())
        return pages

    @staticmethod
    def _parse_pdf(path: str) -> str:
        """PDF 逐页提取文本。

        参数:
            path: PDF 路径

        返回:
            页间双换行拼接的全文
        """
        reader = PdfReader(path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _parse_markdown(path: str) -> str:
        """Markdown 转 HTML 后剥离标签得纯文本。

        参数:
            path: Markdown 路径

        返回:
            纯文本
        """
        with open(path, encoding="utf-8") as f:
            md_content = f.read()
        html = markdown.markdown(md_content)
        clean = re.sub(r"<[^>]+>", "", html)
        return clean

    @staticmethod
    def _parse_txt(path: str) -> str:
        """读取 UTF-8 文本文件。

        参数:
            path: 文本路径

        返回:
            文件内容
        """
        with open(path, encoding="utf-8") as f:
            return f.read()


class TextChunker:
    """递归字符分块器：优先在句号/换行等分隔符处切分。"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """初始化分块参数。

        参数:
            chunk_size: 目标块大小（字符）
            chunk_overlap: 块间重叠字符数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", "。", ".", "！", "?", "？", "! ", "; ", "；", " "]

    def split(self, text: str) -> list[str]:
        """将长文本切分为 chunk 列表。

        参数:
            text: 原始全文

        返回:
            非空 chunk 字符串列表
        """
        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """逐字符累积，达 chunk_size 时在最佳分隔点切分。

        参数:
            text: 待切分文本
            separators: 分隔符优先级列表

        返回:
            chunk 列表
        """
        chunks = []
        current_chunk = ""

        for char in text:
            current_chunk += char
            if len(current_chunk) >= self.chunk_size:
                split_pos = self._find_best_split_point(current_chunk, separators)
                if split_pos > 0:
                    chunks.append(current_chunk[:split_pos].strip())
                    current_chunk = current_chunk[max(0, split_pos - self.chunk_overlap) :]
                else:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _find_best_split_point(self, text: str, separators: list[str]) -> int:
        """在文本后 20% 区域找最接近 chunk_size 的分隔位置。

        参数:
            text: 当前累积块
            separators: 分隔符列表

        返回:
            切分位置（字符索引），-1 表示未找到合适点
        """
        search_start = int(len(text) * 0.8)
        search_area = text[search_start:]
        best_pos = -1

        for sep in separators:
            pos = search_area.rfind(sep)
            if pos != -1:
                actual_pos = search_start + pos + len(sep)
                if abs(actual_pos - self.chunk_size) < abs(best_pos - self.chunk_size):
                    best_pos = actual_pos

        return best_pos if best_pos > 0 else len(text)


@dataclass
class ChunkSegment:
    """结构分块片段（Week 3 G1）。"""

    content: str
    heading_path: str = ""
    page_no: int | None = None


class StructuredTextChunker:
    """结构感知分块：Markdown 按标题、PDF 按页+段落。"""

    def __init__(
        self,
        *,
        max_chars: int = 800,
        min_chars: int = 100,
        chunk_overlap: int = 50,
        noise_min_chars: int = 30,
    ):
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.chunk_overlap = chunk_overlap
        self.noise_min_chars = noise_min_chars
        self._fallback = TextChunker(chunk_size=max_chars, chunk_overlap=chunk_overlap)

    def format_for_ingest(self, seg: ChunkSegment) -> str:
        """将 metadata 写入 chunk 前缀，便于检索命中章节。"""
        body = seg.content.strip()
        if seg.heading_path:
            return f"[章节: {seg.heading_path}]\n{body}"
        if seg.page_no is not None:
            return f"[第{seg.page_no}页]\n{body}"
        return body

    def split_markdown(self, md: str) -> list[ChunkSegment]:
        """按 # 标题分节，节内再切分。"""
        lines = md.splitlines()
        sections: list[tuple[str, list[str]]] = []
        heading_stack: list[tuple[int, str]] = []
        current_path = ""
        current_lines: list[str] = []

        heading_re = re.compile(r"^(#{1,6})\s+(.+)$")

        def flush() -> None:
            nonlocal current_lines, current_path
            text = "\n".join(current_lines).strip()
            if text:
                sections.append((current_path, self._split_body(text, page_no=None)))
            current_lines = []

        for line in lines:
            m = heading_re.match(line.strip())
            if m:
                flush()
                level = len(m.group(1))
                title = m.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                current_path = " > ".join(h for _, h in heading_stack)
                continue
            current_lines.append(line)
        flush()

        segments: list[ChunkSegment] = []
        for path, parts in sections:
            for part in parts:
                segments.append(ChunkSegment(content=part, heading_path=path))
        return self._filter_noise(segments)

    def split_pdf_pages(self, pages: list[str]) -> list[ChunkSegment]:
        """按页 + 段落切分，过滤噪声块。"""
        segments: list[ChunkSegment] = []
        for i, page_text in enumerate(pages, start=1):
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
            merged = self._merge_small_paragraphs(paragraphs)
            for para in merged:
                for part in self._split_body(para, page_no=i):
                    segments.append(ChunkSegment(content=part, page_no=i))
        return self._filter_noise(segments)

    def split_plain(self, text: str) -> list[ChunkSegment]:
        """纯文本：段落优先，fallback 递归分块。"""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text]
        merged = self._merge_small_paragraphs(paragraphs)
        segments: list[ChunkSegment] = []
        for para in merged:
            for part in self._split_body(para, page_no=None):
                segments.append(ChunkSegment(content=part))
        return self._filter_noise(segments)

    def _split_body(self, text: str, *, page_no: int | None) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]
        return self._fallback.split(text)

    def _merge_small_paragraphs(self, paragraphs: list[str]) -> list[str]:
        merged: list[str] = []
        buf = ""
        for p in paragraphs:
            if len(p) < self.min_chars:
                buf = f"{buf}\n\n{p}".strip() if buf else p
                if len(buf) >= self.min_chars:
                    merged.append(buf)
                    buf = ""
                continue
            if buf:
                merged.append(buf)
                buf = ""
            merged.append(p)
        if buf:
            merged.append(buf)
        return merged

    def _filter_noise(self, segments: list[ChunkSegment]) -> list[ChunkSegment]:
        return [s for s in segments if len(s.content.strip()) >= self.noise_min_chars]


def build_document_chunks(
    *,
    file_path: str,
    file_type: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    structured: bool = True,
) -> list[str]:
    """统一入口：解析文件并返回可入库的 chunk 文本列表。"""
    path = str(Path(file_path))
    if structured:
        max_chars = min(max(chunk_size, 300), 800)
        st = StructuredTextChunker(
            max_chars=max_chars,
            min_chars=100,
            chunk_overlap=chunk_overlap,
        )
        if file_type == "md":
            raw = DocumentParser.read_markdown_raw(path)
            segments = st.split_markdown(raw)
        elif file_type == "pdf":
            pages = DocumentParser.parse_pdf_pages(path)
            segments = st.split_pdf_pages(pages) if pages else []
            if not segments:
                text = DocumentParser.parse(path, file_type)
                segments = st.split_plain(text)
        else:
            text = DocumentParser.parse(path, file_type)
            segments = st.split_plain(text)
        return [st.format_for_ingest(s) for s in segments]

    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    text = DocumentParser.parse(path, file_type)
    return chunker.split(text) if text and text.strip() else []


def build_content_chunks(
    content: str,
    *,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    structured: bool = True,
) -> list[str]:
    """对已解析全文做分块（手动录入等无文件路径场景）。"""
    if not content or not content.strip():
        return []
    if structured:
        max_chars = min(max(chunk_size, 300), 800)
        st = StructuredTextChunker(
            max_chars=max_chars,
            min_chars=100,
            chunk_overlap=chunk_overlap,
        )
        segments = st.split_plain(content)
        parts = [st.format_for_ingest(s) for s in segments]
        return parts or [content.strip()]
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.split(content) or [content.strip()]
