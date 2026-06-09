"""SQLAlchemy 异步数据库连接与 Schema 初始化。

导出 `engine`、`async_session`、`Base` 及 `get_db` 依赖注入工厂。
应用启动时由 `init_db()` 建表、执行 SQLite 增量迁移并初始化 FTS5 索引，
是 ORM 模型层与 API/服务层之间的持久化基础设施。
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)


def _sqlite_connect_args(url: str) -> dict:
    """为 SQLite 连接附加超时参数，降低并发写入时的锁冲突概率。

    参数:
        url: 数据库连接 URL。

    返回:
        SQLite 专用 connect_args 字典；非 SQLite 返回空字典。
    """
    if "sqlite" not in url:
        return {}
    return {"timeout": 30}


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=_sqlite_connect_args(settings.DATABASE_URL),
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""

    pass


def import_all_models() -> None:
    """导入全部 ORM 模型，确保 Base.metadata 在 create_all 前已完整注册。"""
    import app.models  # noqa: F401


def expected_table_names() -> set[str]:
    """返回 ORM 定义中期望存在的全部表名。

    返回:
        表名字符串集合。
    """
    import_all_models()
    return set(Base.metadata.tables.keys())


async def existing_table_names() -> set[str]:
    """查询 SQLite 中当前已存在的用户表名。

    返回:
        已存在表名字符串集合（不含 sqlite_ 系统表）。
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        )
        return {row[0] for row in result}


async def verify_schema() -> list[str]:
    """校验数据库 Schema 是否与 ORM 定义一致。

    返回:
        缺失的表名列表；空列表表示 schema 完整。
    """
    expected = expected_table_names()
    existing = await existing_table_names()
    return sorted(expected - existing)


async def get_db() -> AsyncSession:
    """FastAPI 依赖：为每个请求提供异步数据库会话并在结束时关闭。

    返回:
        异步生成器，yield 一个 `AsyncSession` 实例。
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def _apply_sqlite_migrations(conn) -> None:
    """为已有表补充新增列（SQLite create_all 不会 ALTER）。"""
    migrations = [
        ("documents", "ingest_duplicate_count", "INTEGER NOT NULL DEFAULT 0"),
        ("documents", "ingest_conflict_count", "INTEGER NOT NULL DEFAULT 0"),
        ("knowledge_gaps", "document_id", "VARCHAR(36)"),
        ("knowledge_gaps", "parent_gap_id", "VARCHAR(36)"),
        ("knowledge_gaps", "updated_at", "DATETIME"),
        ("knowledge_gaps", "resolved_at", "DATETIME"),
    ]
    for table, column, col_def in migrations:
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        cols = {row[1] for row in result}
        if column not in cols:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
            logger.info("migrate: added %s.%s", table, column)


async def init_db() -> None:
    """创建所有缺失表，并校验 schema 与 ORM 一致。

    流程：启用 WAL → create_all → 增量列迁移 → FTS5 初始化 → 校验表完整性。
    Schema 不完整时抛出 RuntimeError 提示运行修复脚本。
    """
    import_all_models()
    table_names = sorted(Base.metadata.tables.keys())
    logger.info("init_db: registering %d tables: %s", len(table_names), ", ".join(table_names))

    async with engine.begin() as conn:
        if "sqlite" in settings.DATABASE_URL:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
        await conn.run_sync(Base.metadata.create_all)
        await _apply_sqlite_migrations(conn)
        from .fts_init import init_fts_on_connection

        await init_fts_on_connection(conn)

    missing = await verify_schema()
    if missing:
        raise RuntimeError(
            f"Database schema incomplete after create_all. Missing tables: {missing}. "
            f"Run: python scripts/ensure_db_schema.py"
        )
    logger.info("init_db: schema OK (%d tables)", len(table_names))
