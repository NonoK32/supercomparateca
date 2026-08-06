#!/usr/bin/env bash
# Restaura un backup en una base de datos DESECHABLE y cuenta las filas.
#
# Un backup que nunca se ha restaurado no es un backup, es un fichero. Esto es
# lo unico que demuestra que el .sql.gz sirve: se levanta un PostgreSQL
# temporal, se carga el volcado dentro y se cuenta lo que ha entrado. No toca
# en ningun momento la base de datos real.
#
# Uso:  ./scripts/verificar-backup.sh                        el mas reciente
#       ./scripts/verificar-backup.sh backups/xxx.sql.gz     uno concreto
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTENEDOR="verificar-backup-tmp"
# Se usa la misma version mayor que produccion: un dump de 16 puede no cargar
# en una version anterior.
IMAGEN="postgres:16-alpine"

if [ $# -ge 1 ]; then
  dump="$1"
else
  # El mas reciente por fecha de modificacion.
  dump="$(find "$BACKUP_DIR" -name 'supercomparateca-*.sql.gz' -type f \
    -exec ls -t {} + 2>/dev/null | head -1 || true)"
fi

if [ -z "${dump:-}" ] || [ ! -f "$dump" ]; then
  echo "No se encuentra ningun backup que verificar (mire en $BACKUP_DIR)."
  exit 1
fi

echo "Verificando: $dump"
echo "Tamaño comprimido: $(du -h "$dump" | cut -f1)"

# Integridad del gzip antes de montar nada: un fichero truncado (disco lleno,
# copia interrumpida) se detecta aqui en un segundo, y el mensaje deja claro
# que el problema es el fichero y no la base de datos.
if ! gzip -t "$dump" 2>/dev/null; then
  echo
  echo "FALLA: el fichero esta corrupto o incompleto (gzip no puede leerlo)."
  echo "No hace falta mirar mas: ese backup no sirve."
  exit 1
fi

limpiar() { docker rm -f "$CONTENEDOR" >/dev/null 2>&1 || true; }
trap limpiar EXIT
limpiar

echo "Levantando un PostgreSQL desechable..."
docker run --rm -d --name "$CONTENEDOR" \
  -e POSTGRES_PASSWORD=verificacion \
  -e POSTGRES_DB=verificacion \
  "$IMAGEN" >/dev/null

for intento in $(seq 1 30); do
  if docker exec "$CONTENEDOR" pg_isready -U postgres -d verificacion >/dev/null 2>&1; then
    break
  fi
  if [ "$intento" = "30" ]; then
    echo "El PostgreSQL temporal no ha arrancado en 30 s."
    exit 1
  fi
  sleep 1
done

# Los volcados anteriores al 2026-08-06 se hicieron sin --no-owner, asi que
# llevan dentro "OWNER TO <rol>" y no restauran si ese rol no existe. Se crean
# los roles que el propio volcado menciona, para poder verificar tambien los
# backups antiguos (que son justo los que hay que poder recuperar).
roles="$(gzip -dc "$dump" | grep -oE '(OWNER TO|GRANT [A-Z ,]+ ON [^ ]+ TO) [A-Za-z0-9_]+' \
  | awk '{print $NF}' | sort -u | grep -vE '^(postgres|PUBLIC)$' || true)"
if [ -n "$roles" ]; then
  echo "Creando los roles que el volcado da por existentes: $(echo "$roles" | tr '\n' ' ')"
  while IFS= read -r rol; do
    [ -z "$rol" ] && continue
    docker exec "$CONTENEDOR" psql -U postgres -d verificacion -q -c \
      "create role \"$rol\" superuser login" >/dev/null 2>&1 || true
  done <<< "$roles"
fi

echo "Restaurando el volcado..."
# Se captura la salida en vez de tirarla: si la restauracion falla a medias,
# el mensaje de psql es lo unico que dice por que.
if ! salida="$(gzip -dc "$dump" | docker exec -i "$CONTENEDOR" \
    psql -v ON_ERROR_STOP=1 -U postgres -d verificacion 2>&1)"; then
  echo
  echo "FALLA: el backup NO se puede restaurar."
  echo "$salida" | tail -20
  exit 1
fi

echo
echo "Filas restauradas por tabla:"
# Se cuentan las tablas del esquema public, una a una. Nada de estimaciones de
# pg_class: tras un COPY las estadisticas aun no estan actualizadas y darian 0
# en tablas que si tienen datos.
filas_total=0
tablas="$(docker exec "$CONTENEDOR" psql -U postgres -d verificacion -At -c \
  "select tablename from pg_tables where schemaname='public' order by tablename")"

if [ -z "$tablas" ]; then
  echo "  (ninguna tabla)"
else
  while IFS= read -r tabla; do
    [ -z "$tabla" ] && continue
    n="$(docker exec "$CONTENEDOR" psql -U postgres -d verificacion -At -c \
      "select count(*) from \"$tabla\"")"
    printf '  %-20s %s\n' "$tabla" "$n"
    filas_total=$((filas_total + n))
  done <<< "$tablas"
fi

echo
if [ "$filas_total" -eq 0 ]; then
  echo "AVISO: el backup restaura, pero esta VACIO (0 filas en total)."
  echo "El esquema esta, los datos no. Revisar por que el volcado sale sin nada."
  exit 1
fi

echo "Correcto: el backup restaura y contiene $filas_total filas."
