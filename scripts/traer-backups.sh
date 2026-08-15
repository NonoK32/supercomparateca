#!/usr/bin/env bash
# Se trae los backups del servidor a esta maquina. EJECUTAR EN LOCAL, no en el
# servidor.
#
# POR QUE EXISTE: backup-db.sh deja las copias en el propio servidor, en el
# mismo disco que la base de datos. Si se pierde la maquina se pierden las dos
# cosas a la vez, y este servidor ya entro en modo rescate una vez sin que se
# sepa por que. Una copia solo cuenta como copia si esta en otro sitio.
#
# Lo lanza launchd todos los dias (scripts/instalar-copia-local.sh). Corre sin
# nadie delante, asi que: nada de preguntas, se comprueba que lo traido sirve, y
# si algo va mal se avisa por correo en vez de dejarlo en un log.
#
# Uso:  ./scripts/traer-backups.sh
#       DESTINO=~/copias ./scripts/traer-backups.sh
set -uo pipefail

SERVIDOR="${SERVIDOR:-deploy@77.42.30.58}"
REMOTO="${REMOTO:-/opt/supercomparateca/backups}"
DESTINO="${DESTINO:-$HOME/copias-supercomparateca}"
# A partir de aqui la copia de fuera ya no sirve de mucho: son mas de dos noches
# sin backup nuevo, o sea que algo lleva roto por lo menos un dia entero.
HORAS_MAXIMAS="${HORAS_MAXIMAS:-48}"

# Junto al propio script y no via la raiz del repo: launchd ejecuta una copia
# instalada en ~/Library/Application Support, porque macOS no le deja leer
# ~/Documents (ver instalar-copia-local.sh).
aqui="$(cd "$(dirname "$0")" && pwd)"

fallar() {
  echo "FALLO: $1" >&2
  "$aqui/avisar.sh" "La copia de seguridad fuera del servidor ha fallado" \
    "$1

Servidor: $SERVIDOR
Destino:  $DESTINO
Fecha:    $(date '+%Y-%m-%d %H:%M:%S %Z')

Mientras esto no se arregle, los backups existen SOLO en el servidor.
Comprobar a mano:  $aqui/traer-backups.sh" >&2 || true
  exit 1
}

mkdir -p "$DESTINO" || fallar "no se puede escribir en $DESTINO"

echo "Trayendo backups de $SERVIDOR:$REMOTO"
echo "           hacia $DESTINO"

# BatchMode: sin esto, si la clave no esta disponible ssh se queda esperando una
# passphrase que nadie va a teclear, y launchd lo deja colgado en vez de fallar.
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10)

if ! "${SSH[@]}" "$SERVIDOR" true 2>/dev/null; then
  fallar "no se puede entrar por SSH en $SERVIDOR.
Si la clave tiene passphrase, tiene que estar en el llavero para que funcione
sin nadie delante:  ssh-add --apple-use-keychain ~/.ssh/supercomparateca"
fi

# Los backups los escribe root (el cron corre con sudo) y `deploy` no puede
# leerlos directamente, de ahi el sudo remoto. Se empaqueta y se manda por la
# tuberia para no necesitar permisos de escritura en el servidor.
#
# PIPESTATUS y no $?: en `a | b`, el codigo que se ve es el de `b`, asi que un
# tar remoto que falla se daba por bueno mientras el tar local acabara bien.
"${SSH[@]}" "$SERVIDOR" "sudo tar -cf - -C '$REMOTO' ." | tar -xf - -C "$DESTINO"
codigos=("${PIPESTATUS[@]}")
[ "${codigos[0]}" -eq 0 ] || fallar "el servidor no pudo empaquetar $REMOTO (codigo ${codigos[0]})"
[ "${codigos[1]}" -eq 0 ] || fallar "no se pudo desempaquetar en $DESTINO (codigo ${codigos[1]})"

# Que el transporte fuera bien no dice que haya llegado un backup: un directorio
# remoto vacio se copia perfectamente y sin quejarse.
ultimo="$(ls -t "$DESTINO"/supercomparateca-*.sql.gz 2>/dev/null | head -1)"
[ -n "$ultimo" ] || fallar "no hay ningun .sql.gz en $DESTINO despues de copiar"

# Y que exista tampoco dice que lleve datos. Es la misma comprobacion que hace
# backup-db.sh al crearlo, repetida aqui sobre lo que de verdad ha llegado.
filas="$(gzip -dc "$ultimo" | awk '
  /^COPY .* FROM stdin;$/ { dentro = 1; next }
  /^\\\.$/                { dentro = 0; next }
  dentro                  { n++ }
  END                     { print n + 0 }
')"
[ "${filas:-0}" -gt 0 ] || fallar "el backup mas reciente ($ultimo) no tiene ninguna fila"

# La copia puede haber ido bien y aun asi estar todo roto: si el cron del
# servidor lleva dias sin generar nada, aqui se copia lo viejo una y otra vez sin
# que nada chirrie. Esta es la comprobacion que de verdad cubre el fallo.
edad_h=$(( ( $(date +%s) - $(stat -f %m "$ultimo" 2>/dev/null || stat -c %Y "$ultimo") ) / 3600 ))
if [ "$edad_h" -gt "$HORAS_MAXIMAS" ]; then
  fallar "el backup mas reciente tiene $edad_h horas (limite: $HORAS_MAXIMAS).
Fichero: $ultimo
La copia de aqui funciona, pero el servidor no esta generando backups nuevos.
Mirar el cron:  ssh $SERVIDOR 'sudo tail /opt/supercomparateca/backups/backup.log'"
fi

# El acme-*.json lleva la clave privada del certificado: que no quede legible
# para todo el mundo por haberla traido a un portatil.
chmod 600 "$DESTINO"/acme-*.json 2>/dev/null || true
chmod 700 "$DESTINO"

total="$(ls -1 "$DESTINO"/supercomparateca-*.sql.gz 2>/dev/null | wc -l | tr -d ' ')"
echo
echo "Copia correcta: $total backups en $DESTINO"
echo "  mas reciente: $(basename "$ultimo") — $filas filas, $edad_h h de antiguedad"
echo
echo "Para saber si restaura de verdad:  ./scripts/verificar-backup.sh $ultimo"
