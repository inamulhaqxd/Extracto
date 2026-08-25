import hashlib
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Document


class DuplicateDetector:
    def __init__(self, db: AsyncSession):
        self.db = db

    def compute_file_hash(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def check_duplicate(self, file_hash: str, user_id: str) -> Optional[Document]:
        result = await self.db.execute(
            select(Document).where(
                Document.file_hash == file_hash,
                Document.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_duplicate(self, file_path: str, user_id: str) -> Optional[Document]:
        file_hash = self.compute_file_hash(file_path)
        return await self.check_duplicate(file_hash, user_id)
