import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select

from ai_rfp_excel.app.api.auth_utils import hash_password
from ai_rfp_excel.app.database.connection import async_session, init_db
from ai_rfp_excel.app.database.models import User


async def seed() -> None:
    await init_db()
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                (User.email == "admin@extracto.local")
                | (User.email == "admin@tender.local")
                | (User.username == "admin")
            )
        )
        user = result.scalar_one_or_none()
        hashed = hash_password("admin123")
        if user:
            user.hashed_password = hashed
            user.email = "admin@extracto.local"
            user.is_admin = True
            user.is_active = True
            print("Updated existing admin user (admin / admin@extracto.local / admin123)")
        else:
            admin_user = User(
                username="admin",
                email="admin@extracto.local",
                hashed_password=hashed,
                is_admin=True,
                is_active=True,
            )
            session.add(admin_user)
            print("Created new admin user (admin / admin@extracto.local / admin123)")
        await session.commit()

if __name__ == "__main__":
    asyncio.run(seed())
