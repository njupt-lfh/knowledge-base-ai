"""文档解析与分块服务"""

import re
from typing import List

import markdown
from pypdf import PdfReader


class DocumentParser:
    """文件解析器 — 支持 PDF / Markdown / TXT"""

    @staticmethod
    def parse(file_path: str, file_type: str) -> str:
        if file_type == "pdf":
            return DocumentParser._parse_pdf(file_path)
        elif file_type == "md":
            return DocumentParser._parse_markdown(file_path)
        elif file_type == "txt":
            return DocumentParser._parse_txt(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")

    @staticmethod
    def _parse_pdf(path: str) -> str:
        reader = PdfReader(path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _parse_markdown(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            md_content = f.read()
        html = markdown.markdown(md_content)
        clean = re.sub(r"<[^>]+>", "", html)
        return clean

    @staticmethod
    def _parse_txt(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


class TextChunker:
    """文本分块器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", "。", ".", "！", "?", "？", "! ", "; ", "；", " "]

    def split(self, text: str) -> List[str]:
        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        chunks = []
        current_chunk = ""

        for char in text:
            current_chunk += char
            if len(current_chunk) >= self.chunk_size:
                split_pos = self._find_best_split_point(current_chunk, separators)
                if split_pos > 0:
                    chunks.append(current_chunk[:split_pos].strip())
                    current_chunk = current_chunk[max(0, split_pos - self.chunk_overlap):]
                else:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _find_best_split_point(self, text: str, separators: List[str]) -> int:
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
