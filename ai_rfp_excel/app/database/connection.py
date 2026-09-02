from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from ai_rfp_excel.app.config import settings


class Base(DeclarativeBase):
    pass


try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        echo=settings.DEBUG,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
except Exception:
    # Dummy async session maker if asyncpg driver is not installed
    engine = None  # type: ignore
    async_session = async_sessionmaker()  # type: ignore


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
