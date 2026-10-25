#!/usr/bin/env bash
# Резервная копия: том Radicale + база приложения (sqlite3 .backup).
set -euo pipefail

STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$STACK_DIR/backups}"
STAMP="$(date +%F-%H%M)"
mkdir -p "$BACKUP_DIR"

# имя проекта — как его видит compose (учитывает COMPOSE_PROJECT_NAME из .env)
COMPOSE_PROJECT="$(cd "$STACK_DIR" && docker compose config 2>/dev/null | awk '/^name:/{print $2; exit}')"
RADICALE_VOLUME="${COMPOSE_PROJECT:-visitka}_radicale_data"

echo "→ архив тома Radicale ($RADICALE_VOLUME)"
docker run --rm -v "$RADICALE_VOLUME:/data:ro" -v "$BACKUP_DIR:/backup" alpine:3.22 \
  tar czf "/backup/radicale-$STAMP.tgz" -C /data .

echo "→ копия базы приложения"
docker compose -f "$STACK_DIR/compose.yaml" exec -T app \
  python -c "import sqlite3,shutil;src=sqlite3.connect('/data/app.db');dst=sqlite3.connect('/data/app-backup.db');src.backup(dst);dst.close();src.close()"
docker compose -f "$STACK_DIR/compose.yaml" cp app:/data/app-backup.db "$BACKUP_DIR/app-$STAMP.db"
docker compose -f "$STACK_DIR/compose.yaml" exec -T app rm -f /data/app-backup.db

echo "готово: $BACKUP_DIR (radicale-$STAMP.tgz, app-$STAMP.db)"
