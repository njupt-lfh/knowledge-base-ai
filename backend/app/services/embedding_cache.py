"""Embedding LRU 缓存（Phase 2.3）。

职责：
    对 embed_query / embed_image 结果做 SHA256 键 LRU 缓存，
    降低重复文本/图片的 API 调用与延迟。

在流水线中的位置：
    EmbeddingService 内部使用

依赖：无
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class EmbeddingCache:
    """基于 SHA256 键的 LRU 向量缓存。"""

    maxsize: int = 512
    _store: dict[str, list[float]] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    hits: int = 0
    misses: int = 0

    @staticmethod
    def _key(text: str) -> str:
        """将原始文本哈希为缓存键。

        参数:
            text: 原始文本或 img:path 键

        返回:
            SHA256 十六进制字符串
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        """读取缓存向量。

        参数:
            text: 原始文本

        返回:
            向量或 None（未命中）
        """
        k = self._key(text)
        vec = self._store.get(k)
        if vec is not None:
            self.hits += 1
            return vec
        self.misses += 1
        return None

    def set(self, text: str, vector: list[float]) -> None:
        """写入缓存，超出 maxsize 时淘汰最旧项。

        参数:
            text: 原始文本
            vector: 嵌入向量
        """
        k = self._key(text)
        if k in self._store:
            self._store[k] = vector
            return
        while len(self._order) >= self.maxsize and self._order:
            old = self._order.pop(0)
            self._store.pop(old, None)
        self._order.append(k)
        self._store[k] = vector

    def clear(self) -> None:
        """清空缓存与命中统计。"""
        self._store.clear()
        self._order.clear()
        self.hits = 0
        self.misses = 0

    @property
    def stats(self) -> dict[str, int | float]:
        """返回缓存命中率等统计。

        返回:
            hits、misses、size、hit_rate 字典
        """
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._store),
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }
