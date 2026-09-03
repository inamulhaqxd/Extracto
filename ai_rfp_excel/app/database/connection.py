from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from ai_rfp_excel.app.config import settings


class Base(DeclarativeBase):
    pass


db_url = settings.DATABASE_URL
if "sqlite" in db_url and "aiosqlite" not in db_url:
    db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")

try:
    engine = create_async_engine(
        db_url,
        poolclass=NullPool,
        echo=settings.DEBUG,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
except Exception:
    # Fallback to local SQLite engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=NullPool)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


_tables_created = False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    global _tables_created
    if not _tables_created and engine:
        try:
            # Import models to ensure registered on Base
            import ai_rfp_excel.app.database.models  # noqa: F401
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            _tables_created = True
        except Exception:
            pass

    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
