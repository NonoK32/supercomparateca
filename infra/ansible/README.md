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
- `deploy.yml` — clona el repo y levanta el stack de producción con Compose + Traefik.

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
