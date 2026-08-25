import hashlib
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Workbook


class ExcelVersioning:
    def __init__(self, db: AsyncSession):
        self.db = db

    def compute_file_hash(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def check_version(self, file_hash: str, user_id: str) -> Optional[Workbook]:
        result = await self.db.execute(
            select(Workbook).where(
                Workbook.file_hash == file_hash,
                Workbook.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_version(self, filename: str, user_id: str) -> Optional[Workbook]:
        result = await self.db.execute(
            select(Workbook).where(
                Workbook.filename == filename,
                Workbook.user_id == user_id,
            ).order_by(Workbook.version.desc())
        )
        return result.scalar_one_or_none()
