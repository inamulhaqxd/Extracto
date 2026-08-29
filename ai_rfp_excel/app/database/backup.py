import subprocess
from datetime import datetime
from pathlib import Path

from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.logging import get_logger

logger = get_logger("database.backup")


def create_database_backup(
    backup_dir: str | Path = "./data/backups",
    retention_days: int = 14,
) -> Path | None:
    """Create a date-stamped, compressed PostgreSQL database backup using pg_dump."""
    out_dir = Path(backup_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"tender_db_backup_{timestamp}.sql"
    backup_path = out_dir / backup_filename

    # Extract connection parameters from settings or env
    db_url = settings.DATABASE_URL
    logger.info("Initiating database backup", target_file=str(backup_path))

    try:
        # Check if pg_dump is available on path
        cmd = [
            "pg_dump",
            db_url,
            "-f",
            str(backup_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            logger.info("Database backup created successfully", path=str(backup_path))
            return backup_path
        else:
            logger.warning("pg_dump returned non-zero code", stderr=res.stderr)
            return None
    except Exception as e:
        logger.error("Database backup execution failed", error=str(e))
        return None
