"""应用配置管理"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR.parent / ".env")


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
    VOLCENGINE_LLM_MODEL: str = os.getenv(
        "VOLCENGINE_LLM_MODEL", "doubao-seed-1-6-flash-250828"
    )

    # 数据库
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR.parent / 'data' / 'knowledge_base.db'}"
    )
    DATABASE_URL_SYNC: str = DATABASE_URL.replace("+aiosqlite", "")

    # Chroma
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR", str(BASE_DIR.parent / "chroma_data")
    )

    # 文件上传
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR.parent / "uploads"))
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "52428800"))

    # 分块
    DEFAULT_CHUNK_SIZE: int = int(os.getenv("DEFAULT_CHUNK_SIZE", "500"))
    DEFAULT_CHUNK_OVERLAP: int = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "50"))

    # Mock
    LLM_MOCK_MODE: bool = os.getenv("LLM_MOCK_MODE", "false").lower() == "true"


settings = Settings()
