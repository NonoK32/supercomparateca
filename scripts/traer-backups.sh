#!/usr/bin/env bash
# Se trae los backups del servidor a esta maquina. EJECUTAR EN LOCAL, no en el
# servidor.
#
# POR QUE EXISTE: backup-db.sh deja las copias en el propio servidor, en el
# mismo disco que la base de datos. Si se pierde la maquina se pierden las dos
# cosas a la vez, y este servidor ya entro en modo rescate una vez sin que se
# sepa por que. Una copia solo cuenta como copia si esta en otro sitio.
#
# Uso:  ./scripts/traer-backups.sh
#       DESTINO=~/copias ./scripts/traer-backups.sh
set -euo pipefail

SERVIDOR="${SERVIDOR:-deploy@77.42.30.58}"
REMOTO="${REMOTO:-/opt/supercomparateca/backups}"
DESTINO="${DESTINO:-$HOME/copias-supercomparateca}"

mkdir -p "$DESTINO"

echo "Trayendo backups de $SERVIDOR:$REMOTO"
echo "           hacia $DESTINO"

# Los backups los escribe root (el cron corre con sudo) y `deploy` no puede
# leerlos directamente, de ahi el sudo remoto. Se empaqueta y se manda por la
# tuberia para no necesitar permisos de escritura en el servidor.
ssh "$SERVIDOR" "sudo tar -cf - -C '$REMOTO' ." | tar -xf - -C "$DESTINO"

echo
echo "Copias en $DESTINO:"
ls -lh "$DESTINO" | tail -n +2 | awk '{printf "  %-40s %s\n", $9, $5}'

# El acme-*.json lleva la clave privada del certificado: que no quede legible
# para todo el mundo por haberla traido a un portatil.
chmod 600 "$DESTINO"/acme-*.json 2>/dev/null || true
chmod 700 "$DESTINO"

echo
echo "Recuerda: para saber si sirven, ./scripts/verificar-backup.sh <fichero>"
