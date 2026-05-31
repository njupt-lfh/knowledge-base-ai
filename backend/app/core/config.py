"""应用配置管理"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def _normalize_upload_dir() -> str:
    """相对路径固定解析到 backend 目录，避免 uvicorn 工作目录变化导致找不到文件。"""
    raw = os.getenv("UPLOAD_DIR", str(BASE_DIR.parent / "uploads"))
    p = Path(raw)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    else:
        p = p.resolve()
    return str(p)


class Settings:
    APP_NAME: str = "AI 知识库管理平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 火山引擎
    VOLCENGINE_API_KEY: str = os.getenv("VOLCENGINE_API_KEY", "")
    VOLCENGINE_BASE_URL: str = os.getenv(
        "VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
    )
    VOLCENGINE_EMBEDDING_MODEL: str = os.getenv(
        "VOLCENGINE_EMBEDDING_MODEL", "doubao-embedding-text-240715"
    )
    VOLCENGINE_LLM_MODEL: str = os.getenv("VOLCENGINE_LLM_MODEL", "doubao-seed-1-6-flash-250828")

    # 数据库
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR.parent / 'data' / 'knowledge_base.db'}"
    )
    DATABASE_URL_SYNC: str = DATABASE_URL.replace("+aiosqlite", "")

    # Chroma
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR.parent / "chroma_data"))

    # 文件上传（相对路径已归一化为绝对路径）
    UPLOAD_DIR: str = _normalize_upload_dir()
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "52428800"))

    # 分块
    DEFAULT_CHUNK_SIZE: int = int(os.getenv("DEFAULT_CHUNK_SIZE", "500"))
    DEFAULT_CHUNK_OVERLAP: int = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "50"))

    # Mock
    LLM_MOCK_MODE: bool = os.getenv("LLM_MOCK_MODE", "false").lower() == "true"

    # Phase 2.1 Hybrid 检索
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))
    HYBRID_RERANK_ENABLED: bool = os.getenv("HYBRID_RERANK_ENABLED", "true").lower() == "true"
    HYBRID_VECTOR_CANDIDATES: int = int(os.getenv("HYBRID_VECTOR_CANDIDATES", "15"))
    HYBRID_FTS_CANDIDATES: int = int(os.getenv("HYBRID_FTS_CANDIDATES", "15"))
    CONTEXT_MAX_CHARS: int = int(os.getenv("CONTEXT_MAX_CHARS", "4500"))

    # Phase 2.2 Agentic-lite / CRAG-lite
    CRAG_MIN_SCORE: float = float(os.getenv("CRAG_MIN_SCORE", "0.22"))
    CRAG_MIN_OVERLAP: float = float(os.getenv("CRAG_MIN_OVERLAP", "0.12"))
    AGENT_MAX_ROUNDS: int = int(os.getenv("AGENT_MAX_ROUNDS", "2"))

    # Phase 2.3 Token 与效率
    HISTORY_RECENT_TURNS: int = int(os.getenv("HISTORY_RECENT_TURNS", "2"))
    HISTORY_SUMMARY_MAX_CHARS: int = int(os.getenv("HISTORY_SUMMARY_MAX_CHARS", "600"))
    EMBEDDING_CACHE_SIZE: int = int(os.getenv("EMBEDDING_CACHE_SIZE", "512"))
    FTS_INCREMENTAL_SYNC: bool = os.getenv("FTS_INCREMENTAL_SYNC", "true").lower() == "true"

    # Phase 3 轻量知识图谱
    GRAPH_ENABLED: bool = os.getenv("GRAPH_ENABLED", "true").lower() == "true"
    GRAPH_MAX_HOPS: int = int(os.getenv("GRAPH_MAX_HOPS", "2"))
    GRAPH_MAX_TRIPLES_PER_CHUNK: int = int(os.getenv("GRAPH_MAX_TRIPLES_PER_CHUNK", "5"))
    GRAPH_EXTRACTION_MODEL: str = os.getenv("GRAPH_EXTRACTION_MODEL", "")

    # Phase 3 检索 abstention（负例误召回抑制）
    RETRIEVAL_ABSTAIN_ENABLED: bool = (
        os.getenv("RETRIEVAL_ABSTAIN_ENABLED", "true").lower() == "true"
    )
    RETRIEVAL_ABSTAIN_MIN_SCORE: float = float(os.getenv("RETRIEVAL_ABSTAIN_MIN_SCORE", "0.20"))
    RETRIEVAL_ABSTAIN_MIN_OVERLAP: float = float(os.getenv("RETRIEVAL_ABSTAIN_MIN_OVERLAP", "0.10"))

    # Phase 4.1 多模态图片入库
    MULTIMODAL_IMAGE_ENABLED: bool = os.getenv("MULTIMODAL_IMAGE_ENABLED", "true").lower() == "true"
    MAX_IMAGE_UPLOAD_SIZE: int = int(os.getenv("MAX_IMAGE_UPLOAD_SIZE", "10485760"))
    VISION_CAPTION_MODEL: str = os.getenv("VISION_CAPTION_MODEL", "")

    # Phase 4.2 PDF 内嵌图片
    PDF_IMAGE_EXTRACTION_ENABLED: bool = (
        os.getenv("PDF_IMAGE_EXTRACTION_ENABLED", "true").lower() == "true"
    )
    PDF_IMAGE_MIN_DIMENSION: int = int(os.getenv("PDF_IMAGE_MIN_DIMENSION", "32"))
    PDF_IMAGE_MAX_PER_DOCUMENT: int = int(os.getenv("PDF_IMAGE_MAX_PER_DOCUMENT", "30"))

    # Phase 4.3 SIM-RAG
    SIM_RAG_ENABLED: bool = os.getenv("SIM_RAG_ENABLED", "true").lower() == "true"
    SIM_RAG_MAX_SUB_QUERIES: int = int(os.getenv("SIM_RAG_MAX_SUB_QUERIES", "3"))
    SIM_RAG_MIN_COVERAGE: float = float(os.getenv("SIM_RAG_MIN_COVERAGE", "0.5"))
    SIM_RAG_SUBQUERY_MIN_OVERLAP: float = float(os.getenv("SIM_RAG_SUBQUERY_MIN_OVERLAP", "0.15"))

    # Phase 4.4 文件夹监听 / Webhook 增量同步
    SYNC_WATCH_ENABLED: bool = os.getenv("SYNC_WATCH_ENABLED", "false").lower() == "true"
    SYNC_WATCH_INTERVAL_SEC: int = int(os.getenv("SYNC_WATCH_INTERVAL_SEC", "120"))
    SYNC_WEBHOOK_SECRET: str = os.getenv("SYNC_WEBHOOK_SECRET", "")


settings = Settings()
