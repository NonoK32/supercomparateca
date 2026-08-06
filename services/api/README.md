# api

API REST y lógica de negocio en **Python (FastAPI)**.

Responsable de: modelos de datos, endpoints CRUD (productos, supermercados, tickets),
autenticación (JWT), asociación línea↔producto mediante alias y endpoints de
comparación de precios.

Se comunica con `ocr-service` por HTTP interno y con `db` (PostgreSQL) por SQL.

## Estado

- EPIC 1: modelos `Supermercado` y `Producto` + CRUD completo y `/health`.
- EPIC 2: ingesta de tickets (`POST /tickets`) — sube imagen, la envía al
  `ocr-service`, parsea líneas/precios y guarda `Ticket` + `LineaTicket` en
  estado `pendiente`. La imagen se descarta tras el OCR.
- EPIC 3: asociación manual línea↔producto (`POST /lineas/{id}/asociar`) con
  aprendizaje de alias (`AliasProducto`). En la ingesta, si ya hay alias exacto
  para ese supermercado, el producto se asigna automáticamente. El ticket pasa a
  `procesado` cuando todas sus líneas están asociadas.
- EPIC 4: consulta de precios — `GET /productos/{id}/precios` (comparativa entre
  supermercados, precio más reciente) y `GET /productos/{id}/historico`
  (evolución temporal, filtrable por `?supermercado_id=`).
- EPIC 5: autenticación JWT — `POST /auth/registro` y `POST /auth/login`.
  Todos los demás endpoints requieren token (deny by default). Los tickets son
  propiedad del usuario del token; ver/borrar un ticket ajeno devuelve 404.

Seguridad: contraseñas con bcrypt, JWT (HS256), secreto vía `JWT_SECRET_KEY`.
Registro protegido con **Cloudflare Turnstile**: si `TURNSTILE_SECRET_KEY` está
definida, `POST /auth/registro` exige un token válido del widget; si está vacía
(desarrollo y tests) no se verifica nada. La clave de sitio, que es pública, se
sirve en `GET /auth/config` para que el frontend estático no la lleve dentro.
El límite de peticiones de `/auth` lo pone Traefik, no la app (ver
`docker-compose.prod.yml`).
Productos, supermercados y comparativa de precios son datos compartidos (globales).

Variable `OCR_SERVICE_URL` para localizar al `ocr-service` (por defecto
`http://ocr-service:8001`).

## Stack

FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · pytest · ruff.

En dev/tests se usa **SQLite** por defecto; en producción se inyecta `DATABASE_URL`
apuntando a PostgreSQL. El esquema está versionado con **Alembic** (`migraciones/`);
la app no crea tablas al arrancar.

### Migraciones

```bash
.venv/bin/alembic upgrade head                          # aplicar (idempotente)
.venv/bin/alembic revision --autogenerate -m "que hace" # tras tocar models.py
.venv/bin/alembic check                                 # ¿modelos y migraciones divergen?
```

Toda migración debe funcionar en PostgreSQL **y** en SQLite. En el contenedor,
`entrypoint.sh` ejecuta `alembic upgrade head` antes de arrancar uvicorn y aborta
el arranque si falla: es preferible no levantar a servir contra un esquema viejo.

## Desarrollo

```bash
cd services/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"     # instala la app y las dependencias de desarrollo

.venv/bin/ruff check .                 # lint
.venv/bin/pytest -q                    # tests unitarios / de API
.venv/bin/behave                       # tests de aceptación (BDD, en features/)

.venv/bin/alembic upgrade head            # crea/actualiza el esquema (la primera vez)

# JWT_SECRET_KEY es obligatoria (mínimo 32 caracteres) o la app no arranca.
JWT_SECRET_KEY=$(openssl rand -hex 32) .venv/bin/uvicorn app.main:app --reload
```

Ejecutar los dos comandos **desde este directorio**: la URL de SQLite por
defecto y el `env_file` de `config.py` son relativos al directorio de trabajo,
así que lanzarlos desde sitios distintos deja a Alembic y a la app en bases de
datos diferentes.

Docs interactivas (Swagger UI) en `http://127.0.0.1:8000/docs`.

### Estructura

```
app/
├── main.py       # App FastAPI, /health, montaje de routers
├── config.py     # Settings (DATABASE_URL) desde entorno
├── database.py   # Engine, SessionLocal, Base, dependencia get_db
├── models.py     # Modelos SQLAlchemy (Supermercado, Producto)
├── schemas.py    # Esquemas Pydantic (Create/Update/Read)
└── routers/      # Endpoints CRUD por entidad
migraciones/      # Alembic: env.py + versions/
entrypoint.sh     # Migra (alembic upgrade head) y arranca uvicorn en el contenedor
tests/            # pytest (BD SQLite en memoria, aislada por test)
```
