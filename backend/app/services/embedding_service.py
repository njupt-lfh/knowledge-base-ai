"""向量嵌入服务"""

from typing import List

from ..core.config import settings


class EmbeddingService:
    """向量嵌入服务 — 基于火山引擎豆包 Embedding API（Mock 模式）"""

    def __init__(self):
        self.mock_mode = settings.LLM_MOCK_MODE
        self.api_key = settings.VOLCENGINE_API_KEY
        self.base_url = settings.VOLCENGINE_BASE_URL
        self.model_name = settings.VOLCENGINE_EMBEDDING_MODEL

    def embed_query(self, text: str) -> List[float]:
        """将查询文本向量化"""
        if self.mock_mode:
            import hashlib
            # Mock: 用文本的 hash 生成伪向量
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            return [(seed >> i) & 0xFF for i in range(256)]

        # TODO: 接入火山引擎 API
        # from volcenginesdkarkruntime import Ark
        # client = Ark(base_url=self.base_url, api_key=self.api_key)
        # response = client.embeddings.create(model=self.model_name, input=text, encoding_format="float")
        # return response.data[0].embedding
        return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量将文档向量化"""
        return [self.embed_query(text) for text in texts]
