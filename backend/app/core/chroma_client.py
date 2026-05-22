"""Chroma 向量数据库客户端"""

from __future__ import annotations

from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from .config import settings

_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    """获取 Chroma 客户端单例"""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(knowledge_base_id: str) -> chromadb.Collection:
    """获取或创建知识库对应的 Collection"""
    client = get_chroma_client()
    try:
        return client.get_collection(knowledge_base_id)
    except Exception:
        return client.create_collection(
            name=knowledge_base_id,
            metadata={"hnsw:space": "cosine"},
        )


def delete_collection(knowledge_base_id: str):
    """删除知识库对应的 Collection"""
    client = get_chroma_client()
    try:
        client.delete_collection(knowledge_base_id)
    except Exception:
        pass
