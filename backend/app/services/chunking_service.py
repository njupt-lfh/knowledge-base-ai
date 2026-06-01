"""文档解析与分块服务。

职责：
    将 PDF/Markdown/TXT 解析为纯文本，再按 chunk_size/overlap 递归分块，
    为入库流水线提供文本片段。

在流水线中的位置：
    document_service._process_document / ingest_manual → DocumentParser + TextChunker

依赖：无（pypdf、markdown 库）
"""

import re

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
