from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from tgbot.config import DbConfig


def create_postgres_engine(db: DbConfig, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        db.construct_sqlalchemy_url(),
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=5,
        echo=echo,
    )


def create_session_pool(engine: AsyncEngine):
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def verify_runtime_schema(engine: AsyncEngine) -> None:
    """Fail fast when the database is reachable but the required schema is absent."""
    async with engine.connect() as connection:
        await connection.execute(text('SELECT user_id FROM "user" LIMIT 1'))
