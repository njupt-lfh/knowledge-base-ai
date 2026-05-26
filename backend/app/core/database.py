"""SQLAlchemy 数据库连接管理"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def import_all_models() -> None:
    """导入全部 ORM 模型，确保 Base.metadata 在 create_all 前已完整注册。"""
    import app.models  # noqa: F401


def expected_table_names() -> set[str]:
    import_all_models()
    return set(Base.metadata.tables.keys())


async def existing_table_names() -> set[str]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        )
        return {row[0] for row in result}


async def verify_schema() -> list[str]:
    """返回缺失的表名；空列表表示 schema 完整。"""
    expected = expected_table_names()
    existing = await existing_table_names()
    return sorted(expected - existing)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """创建所有缺失表，并校验 schema 与 ORM 一致。"""
    import_all_models()
    table_names = sorted(Base.metadata.tables.keys())
    logger.info("init_db: registering %d tables: %s", len(table_names), ", ".join(table_names))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    missing = await verify_schema()
    if missing:
        raise RuntimeError(
            f"Database schema incomplete after create_all. Missing tables: {missing}. "
            f"Run: python scripts/ensure_db_schema.py"
        )
    logger.info("init_db: schema OK (%d tables)", len(table_names))
