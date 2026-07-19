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

echo "Reconstruyendo y levantando los contenedores..."
docker compose "${compose_files[@]}" up -d --build

docker compose "${compose_files[@]}" ps
echo "Despliegue completado."
