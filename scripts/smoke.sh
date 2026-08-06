#!/usr/bin/env bash
# Smoke test: comprueba que lo DESPLEGADO se comporta bien, no solo que
# responde. healthcheck.sh contesta "esta vivo"; esto contesta "hace lo que
# tiene que hacer".
#
# Existe por una averia real: el 2026-08-06 el registro estuvo abierto en
# produccion con una errata en el .env (TUNRSTILE_SECRET_KEY). Todo respondia
# 200, el healthcheck daba OK, y la unica forma de enterarse fue intentar
# registrar un bot a mano. Estas comprobaciones lo habrian cazado en segundos.
#
# Uso:  ./scripts/smoke.sh              local (puertos publicados)
#       ./scripts/smoke.sh prod         por HTTPS contra DOMAIN (leido de .env)
#       ./scripts/smoke.sh prod --limite  incluye la prueba del rate limit
#
# La prueba del rate limit va aparte porque agota tu propia cuota durante un
# minuto: util tras un despliegue, molesta en un cron.
set -euo pipefail

cd "$(dirname "$0")/.."

modo="${1:-local}"
probar_limite=0
for arg in "$@"; do
  [ "$arg" = "--limite" ] && probar_limite=1
done

if [ "$modo" = "prod" ]; then
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
  fi
  : "${DOMAIN:?falta DOMAIN en .env: no se sabe contra que dominio comprobar}"
  BASE="https://$DOMAIN"
  API="$BASE/api"
else
  BASE="${BASE:-http://localhost:8090}"
  API="${API:-http://localhost:8000}"
fi

fallos=0

ok()   { printf '  OK    %s\n' "$1"; }
mal()  { printf '  FALLA %s\n' "$1"; fallos=$((fallos + 1)); }

# Codigo de estado de una peticion, o 000 si no hubo respuesta.
estado() {
  curl -s -o /dev/null -m 10 -w '%{http_code}' "$@" 2>/dev/null || echo 000
}

echo "Smoke test contra $BASE"

# --- 1. Responde algo ---
codigo="$(estado "$API/health")"
[ "$codigo" = "200" ] && ok "la api responde" || mal "la api devuelve $codigo en /health"

codigo="$(estado "$BASE/")"
[ "$codigo" = "200" ] && ok "el frontend responde" || mal "el frontend devuelve $codigo"

# --- 2. La clave de sitio de Turnstile llega al navegador ---
# Necesario pero NO suficiente: en la averia del 2026-08-06 esta clave estaba
# bien y la secreta no. Por eso ademas se sondea el comportamiento (paso 3).
sitekey="$(curl -s -m 10 "$API/auth/config" 2>/dev/null | sed -n 's/.*"turnstile_site_key":"\([^"]*\)".*/\1/p')"
if [ -n "$sitekey" ]; then
  ok "se sirve la clave de sitio de Turnstile"
elif [ "$modo" = "prod" ]; then
  mal "no hay clave de sitio de Turnstile: el registro no muestra widget"
else
  ok "sin clave de sitio de Turnstile (normal en local)"
fi

# --- 3. El registro rechaza de verdad a los bots ---
# La sonda usa un email QUE YA EXISTE, y se apoya en que el api comprueba
# Turnstile ANTES de mirar la base de datos:
#   400 -> se verifico y fallo   => Turnstile activo
#   409 -> "ya existe ese email" => no se verifico, Turnstile APAGADO
# Asi ninguna de las dos ramas llega a crear un usuario.
if [ "$modo" = "prod" ]; then
  if [ -z "${SMOKE_EMAIL:-}" ]; then
    # No se degrada a "OK" en silencio: es justo el fallo que este script
    # existe para evitar.
    mal "falta SMOKE_EMAIL en .env (un email YA registrado); sin el no se puede comprobar el anti-bot"
  else
    codigo="$(estado -X POST "$API/auth/registro" \
      -H 'Content-Type: application/json' \
      -d "{\"nombre\":\"smoke\",\"email\":\"$SMOKE_EMAIL\",\"password\":\"smoke-test-no-usar\"}")"
    case "$codigo" in
      400) ok "el registro exige Turnstile" ;;
      409) mal "el registro NO verifica Turnstile: esta abierto a bots (revisa TURNSTILE_SECRET_KEY en .env y recrea el contenedor)" ;;
      201) mal "el registro ha CREADO un usuario: SMOKE_EMAIL no existia y ademas no hay anti-bot" ;;
      *)   mal "el registro responde $codigo, que no se esperaba" ;;
    esac
  fi
fi

# --- 4. El envio de correo esta configurado ---
# Sin proveedor, el registro no puede mandar la confirmacion; y como sin
# confirmar no se entra, NADIE podria darse de alta. Mismo motivo que con
# Turnstile: que no se descubra por un usuario que no recibe nada.
if [ "$modo" = "prod" ]; then
  if curl -s -m 10 "$API/auth/config" 2>/dev/null | grep -q '"correo_activo":true'; then
    ok "el envio de correo esta configurado"
  else
    mal "no hay proveedor de correo: nadie puede confirmar su cuenta ni recuperar la contraseña (revisa RESEND_API_KEY)"
  fi
fi

# --- 5. Rate limit (opcional) ---
if [ "$probar_limite" = "1" ]; then
  vistos=""
  for _ in $(seq 1 20); do
    vistos="$vistos $(estado "$API/auth/config")"
  done
  case "$vistos" in
    *429*) ok "el limite de peticiones de /api/auth corta ($vistos)" ;;
    *)     mal "20 peticiones seguidas a /api/auth sin un solo 429: no hay limite ($vistos)" ;;
  esac
fi

echo
if [ "$fallos" -eq 0 ]; then
  echo "Todo correcto."
else
  echo "$fallos comprobacion(es) fallidas."
fi
exit $(( fallos > 0 ? 1 : 0 ))
