#!/usr/bin/env bash
# Manda un aviso por correo con Resend.
#
# POR QUE EXISTE: el backup corre a las 3:00 y la copia fuera del servidor corre
# sola. Un fallo que solo va a parar a un fichero de log no lo lee nadie, y un
# backup que lleva semanas roto se descubre el dia que hace falta restaurar, que
# es justo el dia en el que ya no tiene arreglo.
#
# Uso:  ./scripts/avisar.sh "asunto" "cuerpo"
#
# Configuracion (se busca en este orden y gana lo primero que aparezca):
#   1. El entorno.
#   2. ./.env                                  <- el servidor ya tiene la clave
#   3. ~/.config/supercomparateca/avisos.env   <- el portatil
# Variables: RESEND_API_KEY, AVISO_EMAIL y, opcional, CORREO_REMITENTE.
#
# Sin RESEND_API_KEY o sin AVISO_EMAIL no se envia nada y se escribe por la
# salida de errores. Es lo comodo en desarrollo, pero significa que una
# instalacion sin configurar se queda muda: por eso lo dice en voz alta en vez
# de callarse, y devuelve error.
set -uo pipefail

if [ $# -lt 1 ]; then
  echo 'uso: avisar.sh "asunto" ["cuerpo"]' >&2
  exit 2
fi
asunto="$1"
cuerpo="${2:-}"

cargar() {
  [ -f "$1" ] || return 0
  set -a
  # shellcheck disable=SC1090
  . "$1"
  set +a
}

raiz="$(cd "$(dirname "$0")/.." && pwd)"
[ -n "${RESEND_API_KEY:-}" ] || cargar "$raiz/.env"
[ -n "${RESEND_API_KEY:-}" ] || cargar "$HOME/.config/supercomparateca/avisos.env"

remitente="${CORREO_REMITENTE:-SuperComparateca <no-reply@supercomparateca.com>}"
destino="${AVISO_EMAIL:-}"
marca="[SuperComparateca] $asunto"

# En el Mac, ademas del correo, un aviso del sistema. Es lo unico que se ve sin
# tener que abrir un log, y no necesita ninguna credencial: si el correo no esta
# configurado, esto es lo que evita que el fallo pase inadvertido.
if [ "$(uname)" = "Darwin" ] && command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"${cuerpo%%$'\n'*}\" with title \"SuperComparateca\" subtitle \"$asunto\"" \
    >/dev/null 2>&1 || true
fi

if [ -z "${RESEND_API_KEY:-}" ] || [ -z "$destino" ]; then
  echo "AVISO NO ENVIADO POR CORREO (falta RESEND_API_KEY o AVISO_EMAIL): $marca" >&2
  [ -n "$cuerpo" ] && echo "$cuerpo" >&2
  exit 1
fi

# El JSON se construye con python y no a mano: el cuerpo lleva rutas, comillas y
# saltos de linea de la salida de otro script, y escaparlo con printf es la
# forma tipica de mandar un aviso roto justo el dia que importa.
peticion="$(
  ASUNTO="$marca" CUERPO="$cuerpo" DE="$remitente" PARA="$destino" python3 - <<'PY'
import json, os
print(json.dumps({
    "from": os.environ["DE"],
    "to": [os.environ["PARA"]],
    "subject": os.environ["ASUNTO"],
    "text": os.environ["CUERPO"] or os.environ["ASUNTO"],
}))
PY
)"

# --fail-with-body: sin el, un 4xx de Resend sale con codigo 0 y el aviso se da
# por enviado.
if respuesta="$(curl -sS --fail-with-body -m 20 -X POST https://api.resend.com/emails \
      -H "Authorization: Bearer $RESEND_API_KEY" \
      -H "Content-Type: application/json" \
      -d "$peticion" 2>&1)"; then
  echo "Aviso enviado a $destino: $marca"
else
  echo "AVISO NO ENVIADO (Resend respondio): $respuesta" >&2
  exit 1
fi
