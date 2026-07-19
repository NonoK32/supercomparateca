#!/usr/bin/env bash
# Comprueba que la API y el frontend responden. Sale con código != 0 si algo falla.
# Pensado para cron/monitorización.
#
# Uso:  ./scripts/healthcheck.sh
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000/health}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8090/}"

fallo=0

comprobar() {
  local nombre="$1" url="$2"
  if curl -fsS -m 5 "$url" >/dev/null 2>&1; then
    echo "OK   $nombre ($url)"
  else
    echo "FAIL $nombre ($url)"
    fallo=1
  fi
}

comprobar "api" "$API_URL"
comprobar "frontend" "$FRONTEND_URL"

exit "$fallo"
