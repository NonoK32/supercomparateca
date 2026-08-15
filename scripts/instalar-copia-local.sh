#!/usr/bin/env bash
# Programa la copia diaria de los backups a ESTE Mac (launchd).
#
# POR QUE ASI: el servidor no guarda ninguna credencial de ningun sitio externo,
# asi que quien lo comprometa no puede borrar tambien las copias de fuera. El
# precio es que esto solo corre cuando el Mac esta encendido; launchd lanza la
# tarea al despertar si se salto la hora, y traer-backups.sh avisa si lo mas
# reciente pasa de HORAS_MAXIMAS.
#
# Uso:  ./scripts/instalar-copia-local.sh
#       ./scripts/instalar-copia-local.sh --quitar
set -euo pipefail

raiz="$(cd "$(dirname "$0")/.." && pwd)"
etiqueta="com.supercomparateca.copias"
plist="$HOME/Library/LaunchAgents/$etiqueta.plist"
log="$HOME/Library/Logs/supercomparateca-copias.log"
# Los scripts se COPIAN aqui y launchd ejecuta la copia. No es manía: macOS
# protege ~/Documents, ~/Desktop y ~/Downloads con TCC, y un agente de launchd
# que intenta leer un script de ahi falla con "Operation not permitted". La
# alternativa seria dar Acceso Total al Disco a /bin/bash, que es rebajar los
# permisos de todas las shells del sistema para arreglar esto.
agente="$HOME/Library/Application Support/supercomparateca"

if [ "${1:-}" = "--quitar" ]; then
  launchctl bootout "gui/$(id -u)/$etiqueta" 2>/dev/null || true
  rm -f "$plist"
  rm -rf "$agente"
  echo "Copia diaria desinstalada."
  exit 0
fi

if [ "$(uname)" != "Darwin" ]; then
  echo "Esto es para macOS (launchd). En Linux, la misma idea con un cron de usuario:" >&2
  echo "  30 13 * * * $raiz/scripts/traer-backups.sh >> $log 2>&1" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$(dirname "$log")" "$agente"

# Al reinstalar se refrescan: si cambias los scripts en el repo, vuelve a
# ejecutar esto o launchd seguira con la version vieja.
install -m 755 "$raiz/scripts/traer-backups.sh" "$agente/traer-backups.sh"
install -m 755 "$raiz/scripts/avisar.sh" "$agente/avisar.sh"

cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$etiqueta</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$agente/traer-backups.sh</string>
  </array>
  <!-- A la hora de comer: es cuando el portatil suele estar encendido. Si a esa
       hora estaba apagado, launchd la lanza al despertar. -->
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>30</integer></dict>
  <!-- Y tambien al iniciar sesion, para recuperar los dias que se saltaron. -->
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$log</string>
  <key>StandardErrorPath</key><string>$log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$etiqueta" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"

echo "Copia diaria instalada: $etiqueta (13:30, y al iniciar sesion)"
echo "  Ejecuta: $agente/traer-backups.sh (copia; el original vive en el repo)"
echo "  Log:  $log"
echo "  Ver:  launchctl print gui/$(id -u)/$etiqueta | head -20"
echo "  Ya:   launchctl kickstart -p gui/$(id -u)/$etiqueta"
echo

# --- Comprobaciones de lo que hace falta para que esto funcione solo ---
problemas=0

# Se prueba SIN el agente a proposito. Con el agente cargado esto siempre pasa,
# pero el agente se vacia al reiniciar: comprobar la sesion de ahora daria por
# bueno un montaje que muere en el proximo arranque, callado. Lo que tiene que
# funcionar es que ssh saque la passphrase del llavero el solo.
if ! env -u SSH_AUTH_SOCK ssh -o BatchMode=yes -o ConnectTimeout=10 \
     "${SERVIDOR:-deploy@77.42.30.58}" true 2>/dev/null; then
  problemas=1
  echo "AVISO: se entra por SSH solo mientras el agente tenga la clave." >&2
  echo "  Al reiniciar, la copia dejaria de funcionar. Para que ssh la saque" >&2
  echo "  del llavero sin ayuda, guardala una vez:" >&2
  echo "    ssh-add --apple-use-keychain ~/.ssh/supercomparateca" >&2
  echo "  y añade esto a ~/.ssh/config:" >&2
  echo "    Host 77.42.30.58" >&2
  echo "      User deploy" >&2
  echo "      IdentityFile ~/.ssh/supercomparateca" >&2
  echo "      AddKeysToAgent yes" >&2
  echo "      UseKeychain yes" >&2
  echo >&2
fi

avisos="$HOME/.config/supercomparateca/avisos.env"
if [ ! -f "$avisos" ] && [ -z "${RESEND_API_KEY:-}" ]; then
  problemas=1
  echo "AVISO: sin configurar el correo, un fallo de la copia no te llega." >&2
  echo "  Crea $avisos con:" >&2
  echo "    RESEND_API_KEY=re_..." >&2
  echo "    AVISO_EMAIL=tu@correo" >&2
  echo "  (la clave es la misma que ya usa el api en el servidor)" >&2
  echo >&2
fi

if [ "$problemas" = 0 ]; then
  echo "Todo listo: SSH sin passphrase y avisos por correo configurados."
else
  echo "La tarea esta instalada, pero arregla los avisos de arriba o no servira." >&2
  exit 1
fi
