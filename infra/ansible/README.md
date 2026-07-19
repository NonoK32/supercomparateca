# infra/ansible

Aprovisionamiento del servidor (Hetzner) como código, con **Ansible**.

Instala y configura Docker, firewall, usuarios no-root y demás dependencias del
host de forma **idempotente** (se puede re-ejecutar sin romper nada).

No debe contener secretos en claro: usar Ansible Vault o variables de entorno.
