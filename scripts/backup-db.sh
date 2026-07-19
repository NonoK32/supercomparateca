#!/usr/bin/env bash
# Backup de la base de datos PostgreSQL a un fichero .sql.gz con retención.
# Pensado para cron. Debe ejecutarse desde una máquina con el stack levantado.
#
# Uso:   ./scripts/backup-db.sh
# Cron:  0 3 * * *  cd /opt/supercomparateca && ./scripts/backup-db.sh >> backups/backup.log 2>&1
set -euo pipefail

# Raíz del repo (el script vive en scripts/).
cd "$(dirname "$0")/.."

# Carga POSTGRES_USER / POSTGRES_DB desde .env.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
mkdir -p "$BACKUP_DIR"

stamp="$(date +%Y%m%d-%H%M%S)"
destino="$BACKUP_DIR/supercomparateca-$stamp.sql.gz"

echo "Volcando la base de datos '$POSTGRES_DB'..."
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$destino"
echo "Backup creado: $destino"

# Retención: borra backups más antiguos que RETENTION_DAYS días.
find "$BACKUP_DIR" -name 'supercomparateca-*.sql.gz' -type f -mtime +"$RETENTION_DAYS" -delete
echo "Retención aplicada (>$RETENTION_DAYS días)."
