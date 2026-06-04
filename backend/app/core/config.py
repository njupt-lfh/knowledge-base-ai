"""应用配置管理模块。

从环境变量与 `.env` 加载运行时参数，导出 `Settings` 单例 `settings`。
涵盖 LLM/Embedding、SQLite、Chroma、检索策略、图谱、多模态与同步等开关，
供 `main.py`、服务层与评测脚本统一读取，避免硬编码。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR.parent / ".env")


def _normalize_upload_dir() -> str:
    """将上传目录解析为绝对路径。

    相对路径固定相对于 backend 目录，避免 uvicorn 工作目录变化导致找不到文件。

    返回:
        归一化后的上传目录绝对路径字符串。
    """
    raw = os.getenv("UPLOAD_DIR", str(BASE_DIR.parent / "uploads"))
    p = Path(raw)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    else:
        p = p.resolve()
    return str(p)


class Settings:
    """应用全局配置项集合。

    所有字段在实例化时从环境变量读取，未设置则使用合理默认值。
    按 Phase 分组：基础服务、Hybrid 检索、Agent/CRAG、图谱、多模态、文件夹同步等。
    """

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
    STRUCTURED_CHUNKING_ENABLED: bool = (
        os.getenv("STRUCTURED_CHUNKING_ENABLED", "true").lower() == "true"
    )
    STRUCTURED_CHUNK_MAX_CHARS: int = int(os.getenv("STRUCTURED_CHUNK_MAX_CHARS", "800"))
    STRUCTURED_CHUNK_MIN_CHARS: int = int(os.getenv("STRUCTURED_CHUNK_MIN_CHARS", "100"))

    # Mock
    LLM_MOCK_MODE: bool = os.getenv("LLM_MOCK_MODE", "false").lower() == "true"

    # Phase 2.1 Hybrid 检索
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))
    HYBRID_RERANK_ENABLED: bool = os.getenv("HYBRID_RERANK_ENABLED", "true").lower() == "true"
    HYBRID_VECTOR_CANDIDATES: int = int(os.getenv("HYBRID_VECTOR_CANDIDATES", "30"))
    HYBRID_FTS_CANDIDATES: int = int(os.getenv("HYBRID_FTS_CANDIDATES", "30"))
    HYBRID_RRF_POOL_SIZE: int = int(os.getenv("HYBRID_RRF_POOL_SIZE", "30"))
    CONTEXT_MAX_CHARS: int = int(os.getenv("CONTEXT_MAX_CHARS", "4500"))

    # Week 1 Cross-Encoder 二阶段重排
    CROSS_ENCODER_RERANK_ENABLED: bool = (
        os.getenv("CROSS_ENCODER_RERANK_ENABLED", "true").lower() == "true"
    )
    CROSS_ENCODER_MODEL: str = os.getenv(
        "CROSS_ENCODER_MODEL", "BAAI/bge-reranker-v2-m3"
    )
    CROSS_ENCODER_DEVICE: str = os.getenv("CROSS_ENCODER_DEVICE", "cpu")
    POST_RETRIEVAL_MIN_SCORE: float = float(os.getenv("POST_RETRIEVAL_MIN_SCORE", "0.25"))
    POST_RETRIEVAL_MAX_PER_DOCUMENT: int = int(os.getenv("POST_RETRIEVAL_MAX_PER_DOCUMENT", "2"))

    # Phase 2.2 Agentic-lite / CRAG-lite（RRF 分数尺度约 0.01–0.16，勿用 0.2+ 绝对阈值）
    CRAG_MIN_SCORE: float = float(os.getenv("CRAG_MIN_SCORE", "0.06"))
    CRAG_MIN_OVERLAP: float = float(os.getenv("CRAG_MIN_OVERLAP", "0.10"))
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
    # Phase 3b：lite=Graph-Lite | linear=LinearRAG 实体索引 | legacy=旧 BFS（无 G-L2 硬过滤）
    GRAPH_MODE: str = os.getenv("GRAPH_MODE", "lite").lower().strip()

    # Phase 3b P0：多跳双 anchor 分路 + 评测 SIM-RAG 对齐
    MULTI_HOP_SPLIT_ENABLED: bool = (
        os.getenv("MULTI_HOP_SPLIT_ENABLED", "true").lower() == "true"
    )
    MULTI_HOP_PER_ANCHOR_TOP_K: int = int(os.getenv("MULTI_HOP_PER_ANCHOR_TOP_K", "5"))
    MULTI_HOP_ANCHOR_QUOTA_MIN: int = int(os.getenv("MULTI_HOP_ANCHOR_QUOTA_MIN", "1"))
    MULTI_HOP_EMPTY_FALLBACK_ENABLED: bool = (
        os.getenv("MULTI_HOP_EMPTY_FALLBACK_ENABLED", "true").lower() == "true"
    )
    QUOTE_ANCHOR_FTS_ENABLED: bool = (
        os.getenv("QUOTE_ANCHOR_FTS_ENABLED", "true").lower() == "true"
    )
    QUOTE_ANCHOR_FTS_LIMIT_PER_SPAN: int = int(
        os.getenv("QUOTE_ANCHOR_FTS_LIMIT_PER_SPAN", "3")
    )
    EVAL_SIM_RAG_ENABLED: bool = os.getenv("EVAL_SIM_RAG_ENABLED", "true").lower() == "true"

    # Phase 3 检索 abstention（负例误召回抑制）
    RETRIEVAL_ABSTAIN_ENABLED: bool = (
        os.getenv("RETRIEVAL_ABSTAIN_ENABLED", "true").lower() == "true"
    )
    RETRIEVAL_ABSTAIN_MIN_SCORE: float = float(os.getenv("RETRIEVAL_ABSTAIN_MIN_SCORE", "0.06"))
    RETRIEVAL_ABSTAIN_MIN_OVERLAP: float = float(os.getenv("RETRIEVAL_ABSTAIN_MIN_OVERLAP", "0.12"))
    RETRIEVAL_ABSTAIN_MIN_SUBSTANTIVE: float = float(
        os.getenv("RETRIEVAL_ABSTAIN_MIN_SUBSTANTIVE", "0.10")
    )
    RETRIEVAL_ABSTAIN_MIN_ANCHOR: float = float(os.getenv("RETRIEVAL_ABSTAIN_MIN_ANCHOR", "0.20"))
    RETRIEVAL_ABSTAIN_MIN_ANCHOR_MATCHES: int = int(
        os.getenv("RETRIEVAL_ABSTAIN_MIN_ANCHOR_MATCHES", "2")
    )
    # Phase 1 P1：near_domain 专项拒答（CE < 0.45 且 anchor 不匹配）
    NEAR_DOMAIN_GATE_ENABLED: bool = (
        os.getenv("NEAR_DOMAIN_GATE_ENABLED", "true").lower() == "true"
    )
    NEAR_DOMAIN_CE_MAX: float = float(os.getenv("NEAR_DOMAIN_CE_MAX", "0.45"))

    # Week 0：生成后 grounded 自检（Post-hoc），提升 faithfulness / 负例拒答
    POST_HOC_ANSWER_GUARD_ENABLED: bool = (
        os.getenv("POST_HOC_ANSWER_GUARD_ENABLED", "true").lower() == "true"
    )

    # Phase 2：双路径答案一致性守卫（导师建议 #3）
    ANSWER_CONSISTENCY_ENABLED: bool = (
        os.getenv("ANSWER_CONSISTENCY_ENABLED", "true").lower() == "true"
    )
    CONSISTENCY_ROUTES: str = os.getenv(
        "CONSISTENCY_ROUTES", "relational,comprehensive"
    )
    CONSISTENCY_UNCERTAIN_REFUSE: bool = (
        os.getenv("CONSISTENCY_UNCERTAIN_REFUSE", "true").lower() == "true"
    )

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
