# infra/ansible

Aprovisionamiento del servidor (Hetzner) como código, con **Ansible**, de forma
**idempotente** (NFR4).

## Roles

- **base** — paquetes base, usuario de despliegue con sudo, clave SSH y
  endurecimiento de SSH (sin login de root ni contraseñas).
- **docker** — instala Docker Engine + plugin Compose desde el repo oficial.
- **firewall** — `ufw`: deniega todo lo entrante salvo SSH (22), HTTP (80) y HTTPS (443).

## Playbooks

- `provision.yml` — prepara un servidor recién creado (roles base + docker + firewall).
- `deploy.yml` — clona el repo, levanta el stack de producción con Compose + Traefik
  e instala el mantenimiento programado (tarea 13.5):
  - backup de la base de datos + `acme.json` a diario a las 03:00, con 7 días de
    retención, en `{{ app_dir }}/backups` (modo 0700: contiene datos de usuarios
    y la clave privada del certificado);
  - `healthcheck.sh prod` cada 10 minutos a `/var/log/supercomparateca-health.log`;
  - `logrotate` semanal para ambos logs.

  Ambos cron corren como **root** porque `.env` es `root:root 600`.

## Uso

```bash
# 1. Preparar credenciales/variables (no se versionan los ficheros reales)
cp inventory.example.ini inventory.ini            # ajusta la IP
cp group_vars/all.yml.example group_vars/all.yml  # deploy_ssh_key, repo, etc.

# 2. Instalar las colecciones requeridas
ansible-galaxy collection install -r requirements.yml

# 3. Aprovisionar (primera vez se conecta como root) y desplegar
ansible-playbook provision.yml
ansible-playbook deploy.yml
```

> El servidor debe tener el fichero `.env` con los secretos reales (incluido
> `JWT_SECRET_KEY`, `DOMAIN` y `ACME_EMAIL`) en `{{ app_dir }}`; no está versionado.

## Verificación local

```bash
ansible-playbook --syntax-check provision.yml deploy.yml
ansible-lint provision.yml deploy.yml
```
