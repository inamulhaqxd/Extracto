from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from .models import Base

engine = None
async_session_factory = None


def init_db(database_url: str) -> None:
    global engine, async_session_factory

    kwargs: dict = {"echo": False}
    if not database_url.startswith("sqlite"):
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10

    engine = create_async_engine(database_url, **kwargs)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def get_db() -> AsyncSession:
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
