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
   | Type | **CX22** (2 vCPU, 4 GB) | El más pequeño que aguanta compilar imágenes Docker. En el de 2 GB la build puede morir por OOM. |
   | Networking | IPv4 pública **activada** | Sin IPv4 pública, Let's Encrypt no te alcanza. |
   | SSH keys | marca la del paso 3 | Si se te olvida, Hetzner te manda la contraseña de root por email: peor. |
   | Firewalls / Backups | déjalos vacíos | El firewall lo pone Ansible (`ufw`); los backups los harás tú (tarea 13.5). |
   | Name | `supercomparateca` | |

5. **Create & Buy now**. En unos 30 segundos tienes la IP pública. Cópiala.

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
primera vez todavía se entra como root):

```ini
[web]
supercomparateca ansible_host=203.0.113.10 ansible_user=root
```

Edita `group_vars/all.yml` y pega tu clave **pública** en `deploy_ssh_key`:

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

## Estado al terminar

- [ ] Clave SSH creada, con la privada solo en tu máquina
- [ ] Servidor CX22 con Ubuntu 24.04 e IPv4 pública
- [ ] `provision.yml` en verde, y relanzado sin cambios (idempotencia)
- [ ] Entras como `deploy`; root ya no puede entrar por SSH
- [ ] Dominio comprado con privacidad de WHOIS
- [ ] Registros A (`@` y `www`) apuntando a la IP, TTL 300
- [ ] `verificar-dns.sh` en verde

## Qué viene después

1. **13.3 — ensayo con el staging de Let's Encrypt.** Diez minutos de trabajo
   que te dejan fallar todas las veces que haga falta sin gastar cuota. Hazlo
   antes del primer despliegue real.
2. **Regístrate tú el primero** en cuanto la app esté en pie: el primer usuario
   que se registra es administrador (ver README).
3. **13.5 — cron de backups**, en cuanto tengas datos que te dolería perder.

## Si algo va mal

| Síntoma | Causa habitual |
|---|---|
| `Permission denied (publickey)` al entrar como root | La clave no se marcó al crear el servidor. |
| `Permission denied` como `deploy` tras aprovisionar | `deploy_ssh_key` en `all.yml` no es la pública que estás usando. |
| Ansible falla al conectar tras `provision.yml` | El inventario sigue con `ansible_user=root`: root ya está desactivado. |
| El dominio no resuelve tras horas | Registro A en el sitio equivocado, o el dominio usa los nameservers de otro proveedor. |
| `verificar-dns.sh` da una IP antigua | Caché DNS. El script consulta a 1.1.1.1 justo para evitarlo; espera al TTL. |
