#!/usr/bin/env bash
# Muestra quién ha emitido el certificado que sirve el dominio, y si es de
# staging o de producción de Let's Encrypt.
#
# Sirve para el ensayo de la tarea 13.3: primero se despliega contra la CA de
# staging y se comprueba aquí que el certificado llega; solo entonces se pasa a
# producción.
#
# Uso:  ./scripts/verificar-tls.sh supercomparateca.com
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Uso: $0 <dominio>" >&2
  exit 2
fi

DOMINIO="$1"

# -servername es imprescindible: Traefik decide el certificado por SNI.
cert="$(openssl s_client -connect "${DOMINIO}:443" -servername "$DOMINIO" \
  </dev/null 2>/dev/null | openssl x509 -noout -issuer -subject -dates 2>/dev/null || true)"

if [ -z "$cert" ]; then
  echo "FAIL  no se ha podido obtener el certificado de $DOMINIO:443"
  echo "      ¿Está el stack levantado? ¿Abre el firewall el 443?"
  exit 1
fi

echo "$cert"
echo

emisor="$(printf '%s' "$cert" | grep '^issuer=' || true)"
case "$emisor" in
  *STAGING*|*"Fake LE"*|*"(STAGING)"*)
    echo "STAGING: certificado de pruebas de Let's Encrypt."
    echo "El navegador lo rechazará: es lo esperado. El flujo ACME funciona."
    echo "Para pasar a producción: comenta ACME_CASERVER en .env, borra el"
    echo "volumen de certificados y vuelve a levantar el stack."
    ;;
  *"Let's Encrypt"*|*"E[0-9]"*|*"R[0-9]"*)
    echo "PRODUCCIÓN: certificado válido de Let's Encrypt."
    ;;
  *TRAEFIK*|*"TRAEFIK DEFAULT CERT"*)
    echo "AVISO: Traefik está sirviendo su certificado autofirmado por defecto."
    echo "Aún no ha conseguido emitir uno. Mira los logs del reverse-proxy."
    exit 1
    ;;
  *)
    echo "Emisor no reconocido; revísalo a mano."
    ;;
esac
