#!/usr/bin/env bash
# Backup de la base de datos PostgreSQL a un fichero .sql.gz con retención.
# Pensado para cron. Debe ejecutarse desde una máquina con el stack levantado.
#
# Uso:   ./scripts/backup-db.sh            solo la base de datos
#        ./scripts/backup-db.sh prod       ademas, los certificados (acme.json)
# Cron:  lo instala Ansible (infra/ansible/deploy.yml)
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

compose_files=(-f docker-compose.yml)
if [ "${1:-}" = "prod" ]; then
  # El servicio reverse-proxy (y con el acme.json) solo existe en el override.
  compose_files+=(-f docker-compose.prod.yml)
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
mkdir -p "$BACKUP_DIR"

stamp="$(date +%Y%m%d-%H%M%S)"
destino="$BACKUP_DIR/supercomparateca-$stamp.sql.gz"

echo "Volcando la base de datos '$POSTGRES_DB'..."
docker compose "${compose_files[@]}" exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$destino"
echo "Backup creado: $destino"

# Certificados de Let's Encrypt (13.5). No son imprescindibles —Traefik los
# vuelve a emitir— pero restaurarlos evita gastar cuota de la CA si hay que
# reconstruir el servidor con prisa. Best-effort: si el proxy no esta levantado
# no se aborta el backup de la base de datos, que es lo insustituible.
if [ "${1:-}" = "prod" ]; then
  destino_acme="$BACKUP_DIR/acme-$stamp.json"
  if docker compose "${compose_files[@]}" cp reverse-proxy:/letsencrypt/acme.json "$destino_acme" 2>/dev/null; then
    # Contiene la clave privada del certificado.
    chmod 600 "$destino_acme"
    echo "Certificados copiados: $destino_acme"
  else
    echo "AVISO: no se pudo copiar acme.json (¿reverse-proxy parado?); se continua."
  fi
fi

# Retención: borra backups más antiguos que RETENTION_DAYS días.
find "$BACKUP_DIR" \( -name 'supercomparateca-*.sql.gz' -o -name 'acme-*.json' \) \
  -type f -mtime +"$RETENTION_DAYS" -delete
echo "Retención aplicada (>$RETENTION_DAYS días)."
