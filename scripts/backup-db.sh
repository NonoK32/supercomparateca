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
# 30 dias, no 7: un volcado de esta base ocupa unos pocos KB y el disco son
# 40 GB, asi que apretar la retencion no ahorra nada. Lo que si cuesta caro es
# una corrupcion que se detecta tarde y ya no tiene copia sana detras.
RETENTION_DAYS="${RETENTION_DAYS:-30}"
mkdir -p "$BACKUP_DIR"

stamp="$(date +%Y%m%d-%H%M%S)"
destino="$BACKUP_DIR/supercomparateca-$stamp.sql.gz"
# Se vuelca a un fichero temporal y solo se le pone el nombre bueno si el
# volcado sale entero. Sin esto, un pg_dump que falla a medias deja un .sql.gz
# de tamaño plausible que nadie mira, y la retencion acaba borrando los sanos.
parcial="$destino.parcial"

echo "Volcando la base de datos '$POSTGRES_DB'..."
# --no-owner --no-acl: sin ellos, pg_dump mete "ALTER TABLE ... OWNER TO
# supercomparateca" y "GRANT ..." en el volcado, y restaurar en un PostgreSQL
# limpio falla con `role "supercomparateca" does not exist`. Es decir: el
# backup solo servia en una maquina donde ese rol ya existiera, que es
# justamente lo que NO se puede dar por hecho el dia que haya que reconstruir
# el servidor desde cero. Asi el volcado se restaura en cualquier sitio y los
# objetos quedan a nombre de quien haga la restauracion.
if ! docker compose "${compose_files[@]}" exec -T db \
    pg_dump --no-owner --no-acl -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$parcial"; then
  rm -f "$parcial"
  echo "FALLO: pg_dump no ha terminado. No se ha creado ningun backup."
  exit 1
fi

# Que el fichero exista no significa que lleve datos dentro. Se cuentan las
# filas de los bloques COPY del volcado: un dump con el esquema y cero filas
# pesa casi lo mismo que uno con la base entera, asi que mirar el tamaño no
# distingue nada. Esto corre de madrugada sin nadie delante.
filas="$(gzip -dc "$parcial" | awk '
  /^COPY .* FROM stdin;$/ { dentro = 1; next }
  /^\\\.$/                { dentro = 0; next }
  dentro                  { n++ }
  END                     { print n + 0 }
')"

if [ "$filas" -eq 0 ]; then
  rm -f "$parcial"
  echo "FALLO: el volcado no contiene ninguna fila. No se guarda como backup."
  echo "La base de datos esta vacia o pg_dump no ha visto los datos."
  exit 1
fi

mv "$parcial" "$destino"
echo "Backup creado: $destino ($filas filas)"

# Certificados de Let's Encrypt (13.5). No son imprescindibles —Traefik los
# vuelve a emitir— pero restaurarlos evita gastar cuota de la CA si hay que
# reconstruir el servidor con prisa. Best-effort: si el proxy no esta levantado
# no se aborta el backup de la base de datos, que es lo insustituible.
if [ "${1:-}" = "prod" ]; then
  destino_acme="$BACKUP_DIR/acme-$stamp.json"
  # El error de docker se captura en vez de descartarse: esto corre de
  # madrugada sin nadie mirando, y un aviso que no dice por que fallo obliga a
  # reproducirlo a mano al dia siguiente.
  if salida_acme="$(docker compose "${compose_files[@]}" cp reverse-proxy:/letsencrypt/acme.json "$destino_acme" 2>&1)"; then
    # Contiene la clave privada del certificado.
    chmod 600 "$destino_acme"
    echo "Certificados copiados: $destino_acme"
  else
    echo "AVISO: no se pudo copiar acme.json; se continua. Docker dijo: $salida_acme"
  fi
fi

# Retención: borra backups más antiguos que RETENTION_DAYS días.
find "$BACKUP_DIR" \( -name 'supercomparateca-*.sql.gz' -o -name 'acme-*.json' \) \
  -type f -mtime +"$RETENTION_DAYS" -delete
echo "Retención aplicada (>$RETENTION_DAYS días)."
