"""Chroma 向量数据库客户端封装。

提供持久化客户端单例及按知识库 ID 管理的 Collection 操作。
每个知识库对应一个 Chroma Collection，用于存储 chunk 向量，
与 SQLite 中的 chunk 元数据配合实现语义检索。
"""

from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from .config import settings

_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    """获取 Chroma 持久化客户端单例。

    返回:
        指向 `CHROMA_PERSIST_DIR` 的 PersistentClient 实例。
    """
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(knowledge_base_id: str) -> chromadb.Collection:
    """获取或创建知识库对应的向量 Collection。

    参数:
        knowledge_base_id: 知识库 UUID，同时作为 Collection 名称。

    返回:
        已存在或新建的 Chroma Collection（余弦距离空间）。
    """
    client = get_chroma_client()
    try:
        return client.get_collection(knowledge_base_id)
    except Exception:
        return client.create_collection(
            name=knowledge_base_id,
            metadata={"hnsw:space": "cosine"},
        )


def delete_collection(knowledge_base_id: str):
    """删除知识库对应的 Chroma Collection。

    参数:
        knowledge_base_id: 待删除 Collection 的名称（知识库 ID）。

    说明:
        Collection 不存在时静默忽略，避免删除知识库流程因向量库缺失而中断。
    """
    client = get_chroma_client()
    try:
        client.delete_collection(knowledge_base_id)
    except Exception:
        pass
