"""pytest 全局 fixtures — 测试环境初始化。

验证内容：
  - 默认启用 LLM 模拟模式，避免测试调用真实 API
  - 提供临时文本文件 fixture 供文档解析测试使用

运行方式（在 backend 目录）:
  pytest tests/ -v

预期结果：各测试模块自动加载本配置，无需单独运行。
"""

import os
from pathlib import Path

import pytest

# pytest 使用独立 SQLite，避免写入开发库 data/knowledge_base.db 污染前端列表
_test_root = Path(__file__).resolve().parents[1] / "data"
_test_root.mkdir(parents=True, exist_ok=True)
_test_db = _test_root / "test_knowledge_base.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db.as_posix()}"
# 测试专用 Chroma / 上传目录（CI 无 backend/data 时需先创建）
_chroma_dir = _test_root / "test_chroma"
_upload_dir = _test_root / "test_uploads"
_chroma_dir.mkdir(parents=True, exist_ok=True)
_upload_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("CHROMA_PERSIST_DIR", str(_chroma_dir))
os.environ.setdefault("UPLOAD_DIR", str(_upload_dir))

# 默认开启 LLM 模拟模式，避免单元/集成测试消耗真实 API 额度
os.environ.setdefault("LLM_MOCK_MODE", "true")


@pytest.fixture
def tmp_txt(tmp_path):
    """创建包含两行英文内容的临时 .txt 文件，供 DocumentParser 测试使用。"""
    p = tmp_path / "sample.txt"
    p.write_text("Hello world.\nSecond line.", encoding="utf-8")
    return p
