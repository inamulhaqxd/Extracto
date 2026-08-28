#!/bin/sh
set -e

BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-tender_user}"
POSTGRES_DB="${POSTGRES_DB:-tender_db}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/tender_db_backup_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting automated PostgreSQL backup to $BACKUP_FILE..."

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc | gzip > "$BACKUP_FILE"

echo "[$(date)] Backup completed successfully: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"

# Clean up backups older than RETENTION_DAYS
find "$BACKUP_DIR" -name "tender_db_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Cleaned up backups older than $RETENTION_DAYS days."
