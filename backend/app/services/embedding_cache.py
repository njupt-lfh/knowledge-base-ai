"""Embedding LRU 缓存 — Phase 2.3"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class EmbeddingCache:
    maxsize: int = 512
    _store: dict[str, list[float]] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    hits: int = 0
    misses: int = 0

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        k = self._key(text)
        vec = self._store.get(k)
        if vec is not None:
            self.hits += 1
            return vec
        self.misses += 1
        return None

    def set(self, text: str, vector: list[float]) -> None:
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
        self._store.clear()
        self._order.clear()
        self.hits = 0
        self.misses = 0

    @property
    def stats(self) -> dict[str, int | float]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "size": len(self._store),
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }
