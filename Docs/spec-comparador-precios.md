# SuperComparateca — Especificación del Proyecto

**Objetivo del proyecto:** construir una app útil (comparar precios de Mercadona, Lidl, Dia, Aldi a partir de tickets escaneados) mientras se practican todas las tecnologías pedidas en la oferta de T-Systems (Granada) para pivotar de SFCC a DevOps.

---

## 1. Mapeo con los requisitos de la oferta

| Requisito de la oferta | Cómo lo cubre el proyecto |
|---|---|
| Python + OOP | Backend completo (API, lógica de matching, modelos) |
| Ansible | Provisión del servidor de Hetzner (Docker, firewall, usuarios) |
| Git / GitLab / GitLab-CI | Repo, ramas, pipeline de CI/CD |
| Docker | Contenerización de todos los servicios |
| Bash scripting | Scripts de backup, health-check, despliegue de emergencia |
| Behave | Tests de aceptación (BDD) |
| ReadyAPI / json | Tests de la API REST |
| Security-by-design | Auth, secretos, HTTPS, principio de mínimo privilegio |
| Agile / CI-CD | Tablero Kanban (Jira o GitLab Issues) + pipeline automático |
| Jira | Gestión de tareas de este mismo proyecto |

---

## 2. Alcance por fases

### MVP (Fase 1)
Un solo usuario (tú). Subes la foto de un ticket, el sistema extrae el texto por OCR, tú confirmas manualmente a qué producto corresponde cada línea, y queda guardado con precio/fecha/supermercado. Puedes consultar el histórico y comparar precios entre supermercados.

### Fase 2 — Matching automático
El sistema sugiere/asigna automáticamente el producto a partir del texto del ticket, usando similitud de texto (sin IA compleja, algo tipo "fuzzy matching"). Solo pide confirmación cuando no está seguro.

### Fase 3 — Multiusuario
Tus amigos también pueden registrarse y subir tickets desde el mismo frontend. Los precios se comparten (mismo producto, más datos = comparativa más fiable). Aquí entra de lleno la autenticación, permisos y todo lo de "security-by-design".

### Fase 4 (opcional, extra DevOps) — Migración a Kubernetes
Migrar el despliegue de Docker Compose a un cluster k3s en Hetzner, para aprender orquestación real.

---

## 3. Requisitos funcionales

- **FR1** — Registro/login de usuario (JWT)
- **FR2** — Subida de foto de ticket
- **FR3** — OCR: extraer líneas de texto + precios del ticket
- **FR4** — Indicar/detectar el supermercado del ticket
- **FR5** — Asociar manualmente cada línea del ticket a un producto (o crear uno nuevo si no existe)
- **FR6** — Guardar el histórico de compra (producto, precio, fecha, supermercado)
- **FR7** — Consultar el precio de un producto en los distintos supermercados
- **FR8** — Ver la evolución del precio de un producto en el tiempo
- **FR9** *(Fase 2)* — Sugerencia automática de producto por similitud de texto
- **FR10** *(Fase 3)* — Comparar el coste total de "tu cesta habitual" entre supermercados

---

## 4. Requisitos no funcionales

- **NFR1 — Seguridad:** contraseñas hasheadas (bcrypt), JWT para sesiones, HTTPS end-to-end, secretos fuera del código (variables de entorno / GitLab CI/CD variables)
- **NFR2 — Contenerización:** cada servicio en su propio contenedor, usuarios no-root dentro de las imágenes
- **NFR3 — CI/CD:** pipeline con lint → tests unitarios → tests Behave → build de imagen → push a registry → despliegue automático
- **NFR4 — Infraestructura como código:** todo el aprovisionamiento del servidor vía Ansible, de forma idempotente (se puede ejecutar varias veces sin romper nada)
- **NFR5 — Observabilidad:** logging básico centralizado, health-check endpoint
- **NFR6 — Backups:** script bash + cron para respaldar la base de datos periódicamente

---

## 5. Modelo de datos (entidades principales)

- **Usuario**: id, nombre, email, password_hash, fecha_registro
- **Supermercado**: id, nombre (Mercadona, Lidl, Dia, Aldi)
- **Ticket**: id, usuario_id, supermercado_id, fecha_compra, texto_ocr_bruto, estado (pendiente/procesado) — *(no se guarda la imagen original, solo el texto extraído por OCR, por privacidad y para reducir almacenamiento; la imagen se descarta tras procesarla)*
- **LineaTicket**: id, ticket_id, texto_original, cantidad, precio_unitario, precio_total, producto_id (nullable hasta que se asocie)
- **Producto**: id, nombre_normalizado, categoria, unidad_medida
- **AliasProducto**: id, producto_id, texto_alias, supermercado_id — *(guarda las distintas formas en que un mismo producto aparece escrito en cada ticket, para ir "enseñando" al sistema — clave para la Fase 2)*

---

## 5bis. Resolución de ambigüedad de productos (alias)

Los tickets suelen tener texto incompleto o ambiguo (ej. "LECHE DESNATADA" sin marca ni tamaño, "12 HUEVOS" sin especificar categoría). En vez de intentar adivinar esos datos con reglas, el sistema resuelve la ambigüedad reutilizando alias ya confirmados por el propio usuario, y solo pregunta cuando hace falta:

1. **Alias exacto conocido** — si el texto de la línea coincide exactamente con un alias ya guardado para ese supermercado (tabla `AliasProducto`), se asigna el producto automáticamente. No se pregunta nada.
2. **Alias nuevo (primera vez)** — si el texto no coincide con ningún alias conocido, se le pide al usuario que confirme o cree el producto (con marca, tamaño, categoría, etc.). Esa asociación texto↔producto queda guardada como alias para ese supermercado, de cara al futuro.
3. **Alias parecido pero no exacto (Fase 2)** — si el texto es similar a un alias existente pero no idéntico (ej. "LECHE DESNAT" vs "LECHE DESNATADA"), se calcula una similitud de texto. Por encima de un umbral alto se asigna automático; en zona dudosa se sugiere al usuario con un botón de "¿es este producto?" en vez de pedir que rellene todo de cero.
4. **Corrección siempre disponible** — el alias es una sugerencia por defecto, nunca una regla forzada: el usuario puede corregirlo en cualquier momento (ej. si cambió de marca aunque el ticket diga el mismo texto de siempre).
5. **Extra opcional (más adelante)** — si el ticket incluye código EAN/referencia, se podría consultar una base de datos abierta de productos (ej. Open Food Facts) para autocompletar marca/tamaño sin depender del texto ambiguo del ticket.

Esta lógica afecta a **FR5** (pasa a ser "asociar línea↔producto usando alias, con confirmación manual solo cuando hace falta") y es la base real de **FR9** (Fase 2).

---

## 6. Arquitectura técnica

Servicios, cada uno en su propio contenedor Docker:

1. **api** — Python (FastAPI), lógica de negocio y endpoints REST
2. **ocr-service** — Python, extracción de texto de imágenes (Tesseract)
3. **db** — PostgreSQL
4. **reverse-proxy** — Nginx o Traefik, gestiona HTTPS (Let's Encrypt)
5. **frontend** — interfaz web simple para subir tickets y ver comparativas (incluido desde el MVP)

Comunicación: api ↔ ocr-service vía llamada HTTP interna; api ↔ db vía SQL.

---

## 7. Desglose de tareas (Epics para Jira/GitLab Issues)

- **EPIC 0** — Setup: estructura del repo, README, convenciones de commits
- **EPIC 1** — Modelo de datos + API CRUD básica (productos, supermercados)
- **EPIC 2** — Ingesta de tickets: subida de imagen + OCR
- **EPIC 3** — Asociación manual línea↔producto + guardado de histórico
- **EPIC 4** — Endpoints de comparación y consulta de precios
- **EPIC 4bis** — Frontend web simple (subir ticket, confirmar productos, ver comparativas) — incluido desde el MVP
- **EPIC 5** — Autenticación y autorización
- **EPIC 6** — Dockerización de todos los servicios (Dockerfile + docker-compose)
- **EPIC 7** — Aprovisionamiento del servidor Hetzner con Ansible
- **EPIC 8** — Pipeline CI/CD en GitLab
- **EPIC 9** — Tests: Behave (aceptación) + tests de API (estilo ReadyAPI)
- **EPIC 10** *(Fase 2)* — Matching automático por similitud de texto
- **EPIC 11** *(Fase 3)* — Multiusuario y datos compartidos
- **EPIC 12** *(Fase 4)* — Migración a k3s

---

## 8. Ejemplo de criterio de aceptación (formato Behave/Gherkin)

```gherkin
Escenario: Subir un ticket de Mercadona y detectar productos
  Dado que soy un usuario autenticado
  Cuando subo la foto de un ticket de Mercadona
  Entonces el sistema extrae al menos una línea de producto con precio
  Y el ticket queda en estado "pendiente de asociar"
```

---

## 9. Preguntas abiertas / decisiones pendientes

- ~~¿Nombre del proyecto?~~ → **SuperComparateca** ✅
- ~~¿Guardamos la imagen original del ticket o solo el texto extraído?~~ → **Solo el texto extraído**, la imagen se descarta tras el OCR ✅
- ~~¿Motor de OCR: Tesseract vs. nube?~~ → **Tesseract** (gratis, local, autoalojado; queda aislado en su propio contenedor por si se quiere cambiar más adelante) ✅
- ~~¿Frontend desde el MVP o en Fase 3?~~ → **Desde el MVP**, interfaz web simple ✅
