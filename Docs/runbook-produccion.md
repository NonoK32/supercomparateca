# Runbook: primera puesta en producción

Tareas **13.1** (alta del servidor en Hetzner) y **13.2** (dominio y DNS) de la
EPIC 13. Pensado para hacerse una sola vez, en orden, la primera vez.

Al terminar tendrás un servidor aprovisionado y un dominio apuntando a él,
listo para desplegar. **El despliegue en sí no está en este runbook**: antes
conviene hacer 13.3 (ensayo de certificados con el staging de Let's Encrypt),
por el motivo que se explica al final.

> **Orden importante:** el paso 3 desactiva el login de root por SSH. Si haces
> las cosas en otro orden puedes quedarte fuera de tu propio servidor. Sigue la
> secuencia tal cual.

---

## Antes de empezar

Necesitas, en tu máquina:

```bash
ssh -V              # cualquier OpenSSH reciente
ansible --version   # si falta:  brew install ansible
dig -v              # viene con macOS
nc -h               # para verificar-dns.sh; viene con macOS
```

Y dos cosas que cuestan dinero (poco): una cuenta de Hetzner Cloud (~4 €/mes el
servidor) y un dominio (~10 €/año).

---

## Paso 1 — Clave SSH

La clave es cómo entras al servidor. **La privada no sale nunca de tu máquina** y
no se sube al repositorio.

Si ya tienes una `~/.ssh/id_ed25519.pub` puedes reutilizarla. Si no:

```bash
ssh-keygen -t ed25519 -C "supercomparateca" -f ~/.ssh/supercomparateca
```

Te pedirá una passphrase: **pon una**. Es la única defensa si alguien te copia
el portátil.

Eso genera dos ficheros:

- `~/.ssh/supercomparateca` — **privada**. Nunca se comparte, nunca se sube.
- `~/.ssh/supercomparateca.pub` — **pública**. Esta es la que se pega en Hetzner.

Copia la pública al portapapeles:

```bash
pbcopy < ~/.ssh/supercomparateca.pub
```

**Carga la clave en el agente SSH.** Este paso es obligatorio si le has puesto
passphrase: Ansible abre las conexiones de forma no interactiva y **no puede
pedirte la passphrase**, así que sin esto fallará con un
`Permission denied (publickey,password)` que parece un problema de permisos
cuando en realidad es que la clave está cifrada.

```bash
ssh-add --apple-use-keychain ~/.ssh/supercomparateca   # macOS
ssh-add -l                                             # debe listarla
```

En macOS, `--apple-use-keychain` guarda la passphrase en el Llavero y la clave
se recarga sola tras reiniciar. En Linux es `ssh-add ~/.ssh/supercomparateca`,
y hay que repetirlo en cada sesión salvo que uses un gestor de agente.

---

## Paso 2 — Crear el servidor en Hetzner

1. Regístrate en <https://console.hetzner.cloud> (pide verificación de identidad;
   puede tardar unas horas la primera vez).
2. **New project** → nómbralo `supercomparateca`.
3. Dentro del proyecto: **Security → SSH keys → Add SSH key** y pega la clave
   **pública** del paso 1. Ponle un nombre reconocible.
4. **Servers → Add server**:

   | Campo | Valor | Por qué |
   |---|---|---|
   | Location | Nuremberg o Helsinki | Da igual para latencia desde España; Alemania mantiene los datos en la UE (RGPD). |
   | Image | **Ubuntu 24.04** | Es lo que asume el rol `base` (apt, `sshd_config.d`). |
   | Arquitectura | **x86** (serie CX), no ARM | Ver la nota de abajo. |
   | Type | **CX22** (2 vCPU, 4 GB) | El más pequeño que aguanta compilar imágenes Docker. En el de 2 GB la build puede morir por OOM. |
   | Networking | IPv4 pública **activada** | Sin IPv4 pública, Let's Encrypt no te alcanza. |
   | SSH keys | marca la del paso 3 | Si se te olvida, Hetzner te manda la contraseña de root por email: peor. |
   | Firewalls | **ninguno** | El firewall lo pone Ansible con `ufw`: queda como código y reproducible (NFR4). Tener además el de Hetzner es la trampa clásica de depuración — miras `ufw status`, está bien, y el puerto lo bloquea un segundo firewall que se configura por el panel. Un solo sitio donde mirar. |
   | Backups | **desmarcado** | Son snapshots del disco entero (20% del precio). Resuelven algo distinto de la tarea 13.5, que hace `pg_dump` de los datos (insustituibles y portables). Mientras aprendes vas a recrear el servidor varias veces: lo que te protege es que `provision.yml` sea idempotente, no un snapshot de una máquina a medio configurar. Se pueden activar más adelante. |
   | Volumes | **ninguno** | Los 40 GB del servidor sobran: las imágenes de los tickets se descartan tras el OCR. Ojo al choque de nombres: los `volumes` del `docker-compose.yml` (`pgdata`, `letsencrypt`) son volúmenes de Docker y viven en el disco del propio servidor; no hay que comprar nada. |
   | Name | `supercomparateca` | |

5. **Create & Buy now**. En unos 30 segundos tienes la IP pública. Cópiala.

> **¿x86 (CX) o ARM (CAX)?** Las dos funcionan: todas las imágenes base del
> proyecto son multi-arquitectura y las dependencias con código nativo
> (`psycopg`, `bcrypt`, `pydantic`, `pillow`) publican wheels para `aarch64`.
> ARM sale algo más barato. Aun así, aquí se elige **x86** por la tarea 13.4:
> las imágenes se construirán en GitHub Actions, cuyos runners estándar son
> x86_64. Con un servidor ARM habría que emular con QEMU (lento, y más aún con
> Tesseract) o cambiar de runners. Con x86 no hay nada que reconciliar.

Comprueba que entras (sustituye la IP):

```bash
ssh -i ~/.ssh/supercomparateca root@203.0.113.10
```

La primera vez te pedirá confirmar la huella del host: escribe `yes`. Si entras,
sal con `exit`.

> **Si falla:** casi siempre es que la clave no estaba marcada al crear el
> servidor. Se arregla añadiéndola desde la consola web de Hetzner (Rescue →
> Console) o recreando el servidor: aún no hay nada que perder.

---

## Paso 3 — Aprovisionar con Ansible

Aquí es donde tu código de la EPIC 7 hace su trabajo: usuario de despliegue,
Docker, firewall y endurecimiento de SSH.

```bash
cd infra/ansible
cp inventory.example.ini inventory.ini
cp group_vars/all.yml.example group_vars/all.yml
```

Edita `inventory.ini` con tu IP real (déjalo con `ansible_user=root`: esta
primera vez todavía se entra como root) y con la ruta de tu clave privada:

```ini
[web]
supercomparateca ansible_host=203.0.113.10 ansible_user=root ansible_ssh_private_key_file=~/.ssh/supercomparateca
```

> `ansible_ssh_private_key_file` importa si tienes varias claves (por ejemplo,
> otra para GitHub). Sin ella Ansible prueba las de por defecto y falla con
> `Permission denied (publickey)` aunque el `ssh -i ...` a mano te funcione.

Edita `group_vars/all.yml` y pega tu clave **pública** en `deploy_ssh_key`.
**Este es el campo más peligroso del runbook:** si lo dejas con el valor de
ejemplo, el usuario `deploy` se queda con una clave inválida y, como el playbook
desactiva a la vez el login de root y las contraseñas, **te quedas fuera del
servidor**. Desde el commit `8dd77a1` el playbook aborta antes de tocar nada si
detecta el placeholder, pero revísalo igualmente:

```yaml
deploy_user: deploy
deploy_ssh_key: "ssh-ed25519 AAAA... supercomparateca"
app_dir: /opt/supercomparateca
repo_url: https://github.com/NonoK32/supercomparateca.git
```

> Ninguno de estos dos ficheros se versiona (están en `.gitignore`): contienen
> datos de tu infraestructura real.

Instala las colecciones y lanza:

```bash
ansible-galaxy collection install -r requirements.yml
ansible-playbook provision.yml
```

Debe terminar en verde. **Lo que acaba de pasar:** se creó el usuario `deploy`
con tu clave, se instaló Docker, se activó `ufw` (solo 22, 80 y 443) y **se
desactivó el login de root por SSH**.

Por eso ahora hay que cambiar el inventario al usuario nuevo — a partir de aquí,
root ya no entra:

```ini
[web]
supercomparateca ansible_host=203.0.113.10 ansible_user=deploy
```

Verifica **antes de cerrar la terminal actual** que el usuario nuevo funciona:

```bash
ssh -i ~/.ssh/supercomparateca deploy@203.0.113.10 "docker --version && sudo ufw status"
```

Si eso responde, estás dentro y con Docker. Si no responde, no cierres la sesión
de root que puedas tener abierta hasta arreglarlo.

**El playbook es idempotente:** puedes relanzarlo las veces que quieras. La
segunda vez debería salir casi todo en `ok` y nada en `changed`. Pruébalo — es
la definición práctica de NFR4.

---

## Paso 4 — Comprar el dominio

Cualquier registrador vale. Opciones habituales: Namecheap, Porkbun, Cloudflare
(al coste, pero requiere mover los DNS allí), o cualquier registrador español.

Al comprarlo:

- **Activa la privacidad de WHOIS** si es gratis. Si no, tu nombre, dirección y
  teléfono quedan en un registro público consultable por cualquiera.
- Ignora los extras que te intentarán vender (hosting, email, SSL de pago). El
  certificado te lo dará Let's Encrypt gratis.

---

## Paso 5 — Apuntar el DNS al servidor

En el panel DNS de tu registrador, crea **dos registros A**:

| Tipo | Nombre / Host | Valor | TTL |
|---|---|---|---|
| A | `@` | `203.0.113.10` | 300 (5 min) |
| A | `www` | `203.0.113.10` | 300 |

- `@` significa el dominio raíz (`tudominio.com`).
- **Pon un TTL bajo (300) al principio.** Si te equivocas en la IP, con TTL de
  86400 arrastras el error un día entero. Cuando todo funcione puedes subirlo.
- Si el registrador te obliga a elegir entre "DNS propio" y "redirección web",
  quieres **DNS propio con registros A**. Una redirección web no sirve.

Borra cualquier registro A o CNAME que el registrador haya puesto por defecto
apuntando a su página de aparcamiento.

> **Si usas Cloudflare:** pon los registros en **DNS only** (nube gris), no en
> *Proxied* (naranja, que es el valor por defecto). Con el proxy activo el
> dominio resuelve a IPs de Cloudflare, no a tu servidor: `verificar-dns.sh`
> fallará y Traefik no podrá emitir su certificado. Además, Cloudflare en modo
> *Flexible* delante de un Traefik que redirige 80→443 provoca un **bucle
> infinito de redirecciones**. Si más adelante quieres el proxy, actívalo
> **después** de tener el certificado en el origen y con SSL en *Full (strict)*.

> **No crees registros AAAA todavía**, aunque el servidor tenga IPv6 (Hetzner lo
> da activado y gratis). Si existe un AAAA, Let's Encrypt **prefiere IPv6** para
> el reto HTTP-01: si Traefik no está escuchando ahí, el reto falla y consume
> cuota, con el DNS aparentemente bien puesto y todo funcionando por IPv4. Es un
> fallo desconcertante y fácil de evitar. Añade el AAAA más adelante, si quieres,
> **después** de comprobar que el sitio responde por IPv6.

---

## Paso 6 — Verificar antes de desplegar

Este es el paso que más despliegues salva. **No sigas hasta que salga en verde:**

```bash
./scripts/verificar-dns.sh tudominio.com 203.0.113.10
```

Salida esperada:

```
Comprobando tudominio.com -> 203.0.113.10
OK    resuelve a 203.0.113.10
AVISO puerto 80 sin respuesta (normal si el stack aún no está levantado)
AVISO puerto 443 sin respuesta (normal si el stack aún no está levantado)
```

Los avisos de puertos son normales todavía: aún no has levantado nada. Lo que
importa es el `OK` del primero.

**Por qué esto no es opcional:** Traefik pide el certificado a Let's Encrypt con
el reto **HTTP-01**, que consiste en que Let's Encrypt se conecta a
`http://tudominio.com/` y comprueba que llega a tu servidor. Si el DNS todavía
no resuelve, o resuelve a otra IP, la emisión falla. Y los fallos tienen cuota:
**5 por hora**, y **50 certificados por dominio y semana**. Un bucle de
reintentos con el DNS mal puesto te deja el dominio bloqueado durante horas, sin
forma de acelerarlo.

La propagación suele tardar entre 5 minutos y 2 horas. Si aún no resuelve,
espera y repite; no toques nada más.

---

---

## Paso 7 — Ensayo con el staging de Let's Encrypt (tarea 13.3)

Antes del primer despliegue real se ensaya contra la CA de pruebas. Emite
certificados que el navegador **no** reconoce, pero el flujo ACME es idéntico y
los límites son mucho más altos: puedes fallar todas las veces que haga falta
sin quedarte bloqueado.

**1. Prepara el `.env` en el servidor.** Cópialo a `{{ app_dir }}` con los
secretos reales y, para el ensayo, con la CA de staging descomentada:

```bash
DOMAIN=supercomparateca.com
ACME_EMAIL=tu-email@dominio.com
ACME_CASERVER=https://acme-staging-v02.api.letsencrypt.org/directory
JWT_SECRET_KEY=<openssl rand -hex 32>
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_DB=...
```

**2. Comprueba el DNS antes de levantar nada:**

```bash
./scripts/verificar-dns.sh supercomparateca.com <IP>
```

**3. Levanta el stack** (desde el servidor, en `app_dir`):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**4. Comprueba que el certificado ha llegado:**

```bash
./scripts/verificar-tls.sh supercomparateca.com
```

Debe decir **STAGING**. Si dice que Traefik sirve su certificado por defecto,
el reto ha fallado: mira `docker compose logs reverse-proxy`.

**5. Pasa a producción.** Comenta `ACME_CASERVER` en el `.env` y **borra el
volumen de certificados** — sin esto Traefik reutiliza el de staging:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
docker volume rm supercomparateca_letsencrypt
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
./scripts/verificar-tls.sh supercomparateca.com     # ahora: PRODUCCIÓN
```

## Estado al terminar

- [ ] Clave SSH creada, con la privada solo en tu máquina
- [ ] Servidor CX22 con Ubuntu 24.04 e IPv4 pública
- [ ] `provision.yml` en verde, y relanzado sin cambios (idempotencia)
- [ ] Entras como `deploy`; root ya no puede entrar por SSH
- [ ] Dominio comprado con privacidad de WHOIS
- [ ] Registros A (`@` y `www`) apuntando a la IP, TTL 300
- [ ] `verificar-dns.sh` en verde

## Costes: lo que conviene saber antes de la primera factura

- **Apagar un servidor no detiene el cobro.** En Hetzner se factura por recursos
  reservados, no por uso: un servidor apagado cuesta lo mismo. Para dejar de
  pagar hay que **borrarlo**. (En AWS EC2 es distinto; no generalices.)
- **La IPv4 primaria se factura aparte y sigue corriendo aunque no esté asociada
  a ningún servidor.** Al borrar un servidor, revisa **Primary IPs** y borra las
  que queden huérfanas.
- **Rescalar sube, pero no baja del todo:** CPU y RAM se pueden reducir, pero el
  **disco solo puede crecer**. Un CPX21 (80 GB) no puede pasar a CX22 (40 GB), ni
  siquiera vía snapshot. La forma de "bajar" es **recrear** el servidor y volver
  a lanzar `provision.yml` + `deploy.yml`: para eso la infraestructura es código.
- El requisito de **4 GB de RAM ya no aplica**: venía de compilar las imágenes
  en el servidor, y desde la tarea 13.4 solo se descargan de GHCR. Una máquina
  de 2 GB debería bastar, pero **no está comprobado en caliente**: antes de
  bajar de plan, mira el consumo real con `docker stats` durante un OCR, que es
  el pico. Y recuerda que el disco solo puede crecer (ver arriba).

## Adoptar Alembic en una base de datos que ya existe

**Se hace una sola vez, y hay que hacerlo ANTES de desplegar la versión que
incluye Alembic.** La base de datos de producción se creó con `create_all`, así
que ya tiene las tablas pero **no** tiene la tabla `alembic_version`. Si se
despliega sin más, el `entrypoint.sh` intentará aplicar la migración inicial,
chocará con las tablas existentes (`relation "productos" already exists`) y el
contenedor del `api` no arrancará.

La solución es marcar la migración como aplicada **sin ejecutarla**. Es seguro
porque el esquema que genera la migración inicial es idéntico —columnas, tipos,
nullability, claves foráneas e índices— al que dejó `create_all`.

```bash
# En el servidor, como deploy (con sudo: .env es root:root 600)
cd /opt/supercomparateca

# 0. Backup ANTES de tocar nada. Si algo sale mal, esto es la vuelta atrás.
sudo ./scripts/backup-db.sh prod

# 1. Traer el código nuevo SIN levantar todavía
sudo git pull --ff-only

# 2. Construir la imagen del api (trae alembic y las migraciones)
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml build api

# 3. Marcar la línea base como aplicada, sin ejecutar el DDL.
#    `run` crea un contenedor de un solo uso: no arranca la API.
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm --entrypoint alembic api stamp head

# 4. Comprobar que la BD dice estar al día
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm --entrypoint alembic api current    # debe imprimir la revisión (head)

# 5. Ahora sí, desplegar
sudo ./scripts/deploy.sh prod
```

A partir de aquí el ciclo normal es solo el paso 5: `entrypoint.sh` aplica
`alembic upgrade head` en cada arranque y no hay nada más que hacer a mano.

> Si el paso 3 se olvida, el síntoma es claro: el contenedor del `api` reinicia
> en bucle y `docker compose logs api` muestra `DuplicateTable`. No se pierde
> nada: para el stack, haz el `stamp` y vuelve a levantar.

## Activar el filtro anti-bot del registro (Turnstile)

Mientras `TURNSTILE_SECRET_KEY` esté vacía **el registro está abierto a
cualquiera**, sin verificación. El código no falla si falta: se despliega y no
protege. Para activarlo:

1. En <https://dash.cloudflare.com> → **Turnstile** → *Add widget*. Añade el
   dominio `supercomparateca.com`. No hace falta que el dominio esté
   proxificado por Cloudflare (hoy no lo está: el DNS apunta directo al
   servidor).
2. Copia las dos claves al `.env` del servidor:

   ```bash
   sudo nano /opt/supercomparateca/.env
   # TURNSTILE_SITE_KEY=0x4AAA...      (pública, la ve el navegador)
   # TURNSTILE_SECRET_KEY=0x4AAA...    (secreta, no sale del servidor)
   ```

3. Redespliega para que el `api` recoja las variables:

   ```bash
   cd /opt/supercomparateca && sudo ./scripts/deploy.sh prod
   ```

4. Verifica que la clave de sitio se está sirviendo y que la API rechaza un
   registro sin token:

   ```bash
   curl -s https://supercomparateca.com/api/auth/config
   # -> {"turnstile_site_key":"0x4AAA..."}   (vacío = NO está activo)

   curl -s -X POST https://supercomparateca.com/api/auth/registro \
     -H 'Content-Type: application/json' \
     -d '{"nombre":"bot","email":"bot@example.com","password":"password123"}'
   # -> 400, "No se ha podido verificar que no eres un bot"
   ```

Para ensayar sin cuenta real, Cloudflare publica claves de prueba: sitio
`1x00000000000000000000AA`, y secretas `1x0000000000000000000000000000000AA`
(acepta siempre) o `2x0000000000000000000000000000000AA` (rechaza siempre).

### Límite de peticiones

Independiente de Turnstile y ya activo en cuanto se despliega: Traefik limita
`/api/auth` a **10 peticiones por minuto y IP**, con picos de 5. Cubre tanto el
alta masiva como la fuerza bruta contra el login. Se comprueba así:

```bash
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code} " https://supercomparateca.com/api/auth/config
done; echo
# Las primeras responden 200 y a partir del limite aparecen 429.
```

Si algún día se activa el proxy de Cloudflare (nube naranja), **hay que revisar
esto**: Traefik pasaría a ver las IPs de Cloudflare y el límite se aplicaría por
edge en vez de por visitante. Haría falta `forwardedHeaders.trustedIPs` con los
rangos de CF.

## De dónde salen las imágenes (13.4)

**Producción no compila.** El CI publica las tres imágenes en GHCR al integrar
en `main`, y `deploy.sh prod` hace `pull` + `up -d --no-build`. Ese `--no-build`
es deliberado: si falta una imagen, el despliegue falla en vez de ponerse a
compilar en un servidor de 4 GB.

```
ghcr.io/nonok32/supercomparateca-{api,ocr-service,frontend}:main
ghcr.io/nonok32/supercomparateca-{api,ocr-service,frontend}:<sha>
```

> **Solo la primera vez:** hay que **hacer públicos los tres paquetes** en
> GitHub → Packages → *Package settings* → *Change visibility*. Nacen privados
> aunque el repo sea público, y sin eso el `pull` del servidor dará
> `denied`/`not found`.

### Volver a una versión anterior

`IMAGE_TAG` en el `.env` decide qué se despliega. Por defecto es `main` (lo
último integrado). Para retroceder, pon el **SHA completo** del commit y
redespliega:

```bash
sudo nano /opt/supercomparateca/.env    # IMAGE_TAG=<sha completo>
cd /opt/supercomparateca && sudo ./scripts/deploy.sh prod
```

El SHA sale de `git log --format=%H -5` o de la pestaña Actions. Para volver a
lo último, `IMAGE_TAG=main`.

> Ojo: esto **no revierte las migraciones de base de datos**. Si el commit al
> que vuelves es anterior a una migración ya aplicada, el esquema seguirá
> adelantado. Para cambios de esquema destructivos, restaurar el backup.

### Tras el primer despliegue con imágenes

Las que se compilaron en el servidor quedan ocupando disco. Se liberan con:

```bash
sudo docker image prune -a --filter "until=24h"
```

## ⚠️ Despliegue de la migración `01233e7e156c` (una sola vez)

Esa migración **elimina la columna `tickets.texto_ocr_bruto` y su contenido no
se puede recuperar**. Es intencionado: guardaba el texto íntegro del ticket, que
incluye los 4 últimos dígitos de la tarjeta, el número de fidelización, la hora
exacta y la caja. Pero conviene tener un backup fresco por si acaso.

**Antes de desplegar**, a mano:

```bash
cd /opt/supercomparateca && sudo ./scripts/backup-db.sh prod
```

Después ya se despliega normal. `entrypoint.sh` aplica `alembic upgrade head`
al arrancar el `api`, así que la migración corre sola.

Si alguna vez hiciera falta ese texto, la única copia queda en el `.sql.gz`
anterior a este despliegue. Guárdalo aparte si te importa.

## Comprobar que lo desplegado funciona (smoke test)

`healthcheck.sh` contesta *"está vivo"*. `smoke.sh` contesta *"hace lo que tiene
que hacer"*, que no es lo mismo: el 2026-08-06 el registro estuvo abierto a bots
con los cinco contenedores en verde y el healthcheck dando OK.

`deploy.sh` ya lo ejecuta solo al final, y **falla el despliegue si algo no
cuadra**. Para lanzarlo a mano:

```bash
cd /opt/supercomparateca && sudo ./scripts/smoke.sh prod
sudo ./scripts/smoke.sh prod --limite   # incluye la prueba del rate limit
```

Requiere **`SMOKE_EMAIL` en el `.env`**: el email de una cuenta **que ya
exista** (la tuya vale). Con él, la sonda del anti-bot no crea ningún usuario,
porque el `api` verifica Turnstile *antes* de mirar la base de datos:

| Respuesta a `POST /api/auth/registro` con ese email | Significa |
|---|---|
| `400` | Turnstile está activo ✅ |
| `409` | «ya existe ese email» → **no se verificó nada: el registro está abierto** ❌ |
| `201` | `SMOKE_EMAIL` no existía *y* además no hay anti-bot ❌ |

Si `SMOKE_EMAIL` falta, el smoke test **falla a propósito** en vez de pasar sin
comprobar nada: un chequeo que se salta en silencio es el problema que este
script viene a resolver.

La prueba del rate limit va detrás de `--limite` porque gasta tu propia cuota
durante un minuto: interesa tras un despliegue, molesta en un cron.

## Qué viene después

1. **13.3 — ensayo con el staging de Let's Encrypt.** Diez minutos de trabajo
   que te dejan fallar todas las veces que haga falta sin gastar cuota. Hazlo
   antes del primer despliegue real.
2. **Regístrate tú el primero** en cuanto la app esté en pie: el primer usuario
   que se registra es administrador (ver README).
3. **13.6 — secretos:** el `.env` se sigue copiando a mano.
4. **CD automático:** hoy el despliegue lo lanzas tú por SSH. En pausa
   deliberada mientras la EPIC 12 (k3s) siga en pie, porque es la parte que se
   reescribiría.

## Si algo va mal

| Síntoma | Causa habitual |
|---|---|
| El tipo de servidor aparece como no disponible | Capacidad agotada en esa ubicación. Prueba otra (Núremberg, Helsinki) o la serie **CPX** (AMD, también x86). **Nunca la serie CAX**: es ARM y el rol de Docker fija `arch=amd64`. |
| `Permission denied (publickey)` al entrar como root | La clave no se marcó al crear el servidor. |
| `Permission denied` como `deploy` tras aprovisionar | `deploy_ssh_key` en `all.yml` no es la pública que estás usando. |
| `Permission denied (publickey)` en Ansible, pero `ssh -i ...` sí entra | La clave tiene passphrase y no está en el agente: `ssh-add -l` lo confirma. Ansible no puede pedirla. También puede faltar `ansible_ssh_private_key_file` en el inventario. |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | Recreaste el servidor y reutilizas la IP. Verifica la huella contra la que muestra el panel y luego `ssh-keygen -R <IP>`. |
| La clave está en **Security → SSH keys** pero el servidor la rechaza | Tener la clave en la cuenta no la aplica sola: hay que marcarla en el formulario de **cada** servidor al crearlo. |
| **Fuera del servidor: ni `root` ni `deploy` entran tras aprovisionar** | `deploy_ssh_key` no era una clave válida. Recupéralo con **Rebuild** desde el panel (mantiene servidor e IP y reaplica las claves asignadas), corrige `all.yml` y relanza. No hace falta borrar el servidor. |
| Ansible falla al conectar tras `provision.yml` | El inventario sigue con `ansible_user=root`: root ya está desactivado. |
| El dominio no resuelve tras horas | Registro A en el sitio equivocado, o el dominio usa los nameservers de otro proveedor. |
| `verificar-dns.sh` da una IP antigua | Caché DNS. El script consulta a 1.1.1.1 justo para evitarlo; espera al TTL. |
