"""向量嵌入服务 — 火山引擎 Doubao-embedding-vision（多模态 API）"""

from typing import List

from volcenginesdkarkruntime import Ark

from ..core.config import settings
from .embedding_cache import EmbeddingCache

_shared_cache: EmbeddingCache | None = None


def get_embedding_cache() -> EmbeddingCache:
    global _shared_cache
    if _shared_cache is None:
        _shared_cache = EmbeddingCache(maxsize=getattr(settings, "EMBEDDING_CACHE_SIZE", 512))
    return _shared_cache


class EmbeddingService:
    def __init__(self):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.base_url = settings.VOLCENGINE_BASE_URL
        self.model_name = settings.VOLCENGINE_EMBEDDING_MODEL
        self.mock_mode = settings.LLM_MOCK_MODE
        self.cache = get_embedding_cache()

    def _get_client(self) -> Ark:
        return Ark(base_url=self.base_url, api_key=self.api_key)

    def embed_query(self, text: str) -> List[float]:
        """将查询文本向量化（带 LRU 缓存）。"""
        cached = self.cache.get(text)
        if cached is not None:
            return cached

        if self.mock_mode:
            import hashlib

            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            vec = [(seed >> i) & 0xFF for i in range(256)]
            self.cache.set(text, vec)
            return vec

        client = self._get_client()
        response = client.multimodal_embeddings.create(
            model=self.model_name,
            input=[{"type": "text", "text": text}],
            encoding_format="float",
        )
        vec = response.data.embedding
        self.cache.set(text, vec)
        return vec

    def embed_image(self, image_path: str) -> List[float]:
        """图片多模态向量化（与文本同一 embedding 空间）。"""
        from .media_utils import image_to_data_url

        cache_key = f"img:{image_path}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.mock_mode:
            import hashlib

            seed = int(hashlib.md5(cache_key.encode()).hexdigest()[:8], 16)
            vec = [(seed >> i) & 0xFF for i in range(256)]
            self.cache.set(cache_key, vec)
            return vec

        client = self._get_client()
        data_url = image_to_data_url(image_path)
        response = client.multimodal_embeddings.create(
            model=self.model_name,
            input=[{"type": "image_url", "image_url": {"url": data_url}}],
            encoding_format="float",
        )
        vec = response.data.embedding
        self.cache.set(cache_key, vec)
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量向量化：相同文本只 embed 一次（缓存 + 去重）。"""
        if not texts:
            return []
        unique: dict[str, List[float]] = {}
        for t in texts:
            if t not in unique:
                unique[t] = self.embed_query(t)
        return [unique[t] for t in texts]
