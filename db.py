"""数据库连接与会话工厂。

说明：
- 这里仅维护 SQLAlchemy async engine / sessionmaker
- 结构迁移由 Alembic 负责，不在运行时自动建表
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from settings import settings


engine: AsyncEngine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """保留启动钩子。

    当前阶段 DB 连通性由迁移和测试覆盖，这里不做额外动作。
    """
    return None


async def close_db() -> None:
    """应用关闭时释放连接池。"""
    await engine.dispose()
