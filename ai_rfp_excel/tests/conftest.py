import asyncio
import os
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models import Base
from app.database.connection import get_db

TEST_DATABASE_URL = "postgresql+asyncpg://tender_user:tender_password@localhost:5432/tender_test_db"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_test_session() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session_with_user(db_session: AsyncSession) -> AsyncSession:
    from app.database.models import User
    from app.api.auth import get_password_hash

    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        is_admin=False,
    )
    db_session.add(user)
    await db_session.flush()

    return db_session


@pytest_asyncio.fixture(scope="function")
async def admin_session(db_session: AsyncSession) -> AsyncSession:
    from app.database.models import User
    from app.api.auth import get_password_hash

    admin = User(
        id=uuid4(),
        name="Admin User",
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword"),
        is_admin=True,
    )
    db_session.add(admin)
    await db_session.flush()

    return db_session
