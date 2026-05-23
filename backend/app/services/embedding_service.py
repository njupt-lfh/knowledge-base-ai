"""向量嵌入服务 — 火山引擎 Doubao-embedding-vision（多模态 API）"""

from typing import List

from volcenginesdkarkruntime import Ark

from ..core.config import settings


class EmbeddingService:
    def __init__(self):
        self.api_key = settings.VOLCENGINE_API_KEY
        self.base_url = settings.VOLCENGINE_BASE_URL
        self.model_name = settings.VOLCENGINE_EMBEDDING_MODEL
        self.mock_mode = settings.LLM_MOCK_MODE

    def _get_client(self) -> Ark:
        return Ark(base_url=self.base_url, api_key=self.api_key)

    def embed_query(self, text: str) -> List[float]:
        """将查询文本向量化"""
        if self.mock_mode:
            import hashlib
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            return [(seed >> i) & 0xFF for i in range(256)]

        client = self._get_client()
        response = client.multimodal_embeddings.create(
            model=self.model_name,
            input=[{"type": "text", "text": text}],
            encoding_format="float",
        )
        return response.data.embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量将文档向量化（逐条调用）"""
        return [self.embed_query(text) for text in texts]
