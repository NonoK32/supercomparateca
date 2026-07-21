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
  local nombre="$1" ip=""

  # DNS sobre HTTPS primero. Muchos ISP interceptan el puerto 53 y responden
  # ellos aunque preguntes a 1.1.1.1: dig descarta esa respuesta ("reply from
  # unexpected source") y devuelve vacio, lo que parecia "no resuelve". DoH va
  # por 443 cifrado y no se puede interceptar asi.
  if command -v curl >/dev/null 2>&1; then
    ip="$(curl -s -m 10 -H 'accept: application/dns-json' \
      "https://cloudflare-dns.com/dns-query?name=${nombre}&type=A" 2>/dev/null \
      | tr ',' '\n' | grep -o '"data":"[0-9.]\{7,\}"' | cut -d'"' -f4 | tail -1)"
  fi

  # Respaldo si no hay curl o no hay salida a internet por HTTPS.
  if [ -z "$ip" ] && command -v dig >/dev/null 2>&1; then
    ip="$(dig +short A "$nombre" @1.1.1.1 | tail -1)"
  fi
  if [ -z "$ip" ]; then
    ip="$(getent hosts "$nombre" 2>/dev/null | awk '{print $1}' | tail -1)"
  fi

  echo "$ip"
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
#
# Se usa curl y no nc porque `nc -w` no acota la conexion en todas las
# plataformas: contra una IP que descarta los paquetes en silencio se queda
# colgado. --connect-timeout si es un limite duro.
for puerto in 80 443; do
  if curl -s -o /dev/null --connect-timeout 5 -m 8 "http://$IP_ESPERADA:$puerto/" 2>/dev/null; then
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
