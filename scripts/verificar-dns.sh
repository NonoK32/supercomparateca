#!/usr/bin/env bash
# Comprueba que el dominio ya apunta al servidor ANTES de arrancar Traefik.
#
# Let's Encrypt valida con el reto HTTP-01: se conecta a http://DOMINIO/ y
# espera encontrar tu servidor. Si el DNS todavía no resuelve (o resuelve a
# otra IP), la emisión falla y cada intento consume cuota: 5 fallos por hora y
# 50 certificados por dominio y semana. Por eso esto se comprueba antes.
#
# Uso:  ./scripts/verificar-dns.sh supercomparateca.example.com 203.0.113.10
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Uso: $0 <dominio> <ip-del-servidor>" >&2
  exit 2
fi

DOMINIO="$1"
IP_ESPERADA="$2"
fallo=0

resolver() {
  # Se consulta a un resolver público: el DNS de tu router/ISP puede tener
  # cacheada la respuesta antigua y darte un falso positivo (o negativo).
  if command -v dig >/dev/null 2>&1; then
    dig +short A "$1" @1.1.1.1 | tail -1
  else
    getent hosts "$1" | awk '{print $1}' | tail -1
  fi
}

echo "Comprobando $DOMINIO -> $IP_ESPERADA"

ip_real="$(resolver "$DOMINIO")"
if [ -z "$ip_real" ]; then
  echo "FAIL  el dominio no resuelve todavía (la propagación puede tardar)"
  fallo=1
elif [ "$ip_real" != "$IP_ESPERADA" ]; then
  echo "FAIL  resuelve a $ip_real, no a $IP_ESPERADA"
  fallo=1
else
  echo "OK    resuelve a $ip_real"
fi

# Puerto 80: imprescindible para el reto HTTP-01, aunque luego todo vaya por
# HTTPS. Si el firewall lo bloquea, el certificado no se emite.
for puerto in 80 443; do
  if nc -z -w 5 "$IP_ESPERADA" "$puerto" 2>/dev/null; then
    echo "OK    puerto $puerto abierto en $IP_ESPERADA"
  else
    echo "AVISO puerto $puerto sin respuesta (normal si el stack aún no está levantado)"
  fi
done

if [ "$fallo" -ne 0 ]; then
  echo
  echo "No despliegues todavía: espera a que el DNS propague y vuelve a probar."
fi

exit "$fallo"
