#!/usr/bin/env bash
# Despliegue de emergencia / actualización: trae los últimos cambios y
# reconstruye los contenedores. Ejecutar en el servidor, en la raíz del repo.
#
# Uso:  ./scripts/deploy.sh                 (desarrollo/local)
#       ./scripts/deploy.sh prod            (con el override de producción)
set -euo pipefail

cd "$(dirname "$0")/.."

compose_files=(-f docker-compose.yml)
if [ "${1:-}" = "prod" ]; then
  compose_files+=(-f docker-compose.prod.yml)
fi

echo "Actualizando el código..."
git pull --ff-only

if [ "${1:-}" = "prod" ]; then
  # Produccion no compila: descarga las imagenes que el CI publico en GHCR.
  # --no-build hace que, si falta alguna, esto falle en vez de ponerse a
  # compilar en un servidor de 4 GB (que es de donde veniamos).
  echo "Descargando imagenes..."
  docker compose "${compose_files[@]}" pull
  echo "Levantando los contenedores..."
  docker compose "${compose_files[@]}" up -d --no-build
else
  echo "Reconstruyendo y levantando los contenedores..."
  docker compose "${compose_files[@]}" up -d --build
fi

docker compose "${compose_files[@]}" ps

# Un contenedor "Up" no significa que la aplicacion funcione: el 2026-08-06 el
# registro estuvo abierto a bots con todo en verde. Se comprueba el
# comportamiento antes de dar el despliegue por bueno.
echo
echo "Esperando a que la aplicacion levante..."
modo="${1:-local}"
if [ "$modo" = "prod" ]; then
  sonda="https://$(grep -E '^DOMAIN=' .env | cut -d= -f2-)/api/health"
else
  sonda="http://localhost:8000/health"
fi

for intento in $(seq 1 30); do
  if curl -fsS -m 5 "$sonda" >/dev/null 2>&1; then
    break
  fi
  if [ "$intento" = "30" ]; then
    echo "La api no responde en $sonda tras 60 s. Revisa: docker compose logs api"
    exit 1
  fi
  sleep 2
done

echo "Comprobando el comportamiento..."
if ./scripts/smoke.sh "$modo"; then
  echo "Despliegue completado."
else
  echo
  echo "DESPLIEGUE LEVANTADO PERO CON FALLOS: revisa la lista de arriba."
  echo "Los contenedores estan corriendo; corrige y vuelve a ejecutar este script."
  exit 1
fi
