#!/usr/bin/env bash
# Comprueba que la API y el frontend responden. Sale con código != 0 si algo falla.
# Pensado para cron/monitorización.
#
# Uso:  ./scripts/healthcheck.sh          local: puertos publicados en localhost
#       ./scripts/healthcheck.sh prod     por HTTPS contra DOMAIN (leido de .env)
#
# El modo prod es necesario porque docker-compose.prod.yml deja de publicar los
# puertos de api y frontend (todo entra por Traefik): sondear localhost alli
# fallaria siempre.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "${1:-}" = "prod" ]; then
  # DOMAIN vive en .env, que es la unica fuente de verdad del dominio.
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
  fi
  : "${DOMAIN:?falta DOMAIN en .env: no se sabe contra que dominio comprobar}"
  API_URL="${API_URL:-https://$DOMAIN/api/health}"
  FRONTEND_URL="${FRONTEND_URL:-https://$DOMAIN/}"
else
  API_URL="${API_URL:-http://localhost:8000/health}"
  FRONTEND_URL="${FRONTEND_URL:-http://localhost:8090/}"
fi

fallo=0

comprobar() {
  local nombre="$1" url="$2"
  # Fecha en cada linea: sin ella el log del cron no dice cuando ocurrio el fallo.
  local ahora
  ahora="$(date '+%Y-%m-%d %H:%M:%S')"
  if curl -fsS -m 5 "$url" >/dev/null 2>&1; then
    echo "$ahora OK   $nombre ($url)"
  else
    echo "$ahora FAIL $nombre ($url)"
    fallo=1
  fi
}

comprobar "api" "$API_URL"
comprobar "frontend" "$FRONTEND_URL"

exit "$fallo"
