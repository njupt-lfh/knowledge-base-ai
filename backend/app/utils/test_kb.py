"""识别 pytest / 联调脚本产生的测试知识库，避免污染前端列表与统计。"""

from __future__ import annotations

from sqlalchemy import ColumnElement, not_

# pytest fixture 与 verify/smoke 脚本统一使用 kb-{tag}- 前缀
_TEST_ID_PREFIX = "kb-"

# 少数联调脚本用短名 + 非 kb- ID 时的兜底（正式库极少用单字母名）
_TEST_NAMES = frozenset(
    {
        "t",
        "g",
        "inc",
        "sync",
        "sync-api",
        "fts-test",
        "toggle-kb",
        "upload-kb",
        "manual-kb",
        "p43",
        "p44",
        "p4",
        "p3",
        "fts-verify",
        "x",
    }
)


def is_test_knowledge_base(kb_id: str, name: str | None = None) -> bool:
    """判断是否为测试/联调知识库（不应出现在前端列表）。"""
    if kb_id.startswith(_TEST_ID_PREFIX):
        return True
    n = (name or "").strip()
    if n in _TEST_NAMES:
        return True
    if n.startswith("conflict-kb-"):
        return True
    if n.startswith("PDF联调-") or n.startswith("图片联调-"):
        return True
    return False


def production_kb_clause(model) -> ColumnElement[bool]:
    """SQLAlchemy 过滤条件：排除 id 以 kb- 开头的测试库。"""
    return not_(model.id.like(f"{_TEST_ID_PREFIX}%"))
