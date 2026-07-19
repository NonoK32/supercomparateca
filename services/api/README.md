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

Variable `OCR_SERVICE_URL` para localizar al `ocr-service` (por defecto
`http://ocr-service:8001`).

## Stack

FastAPI · SQLAlchemy 2.0 · Pydantic v2 · pytest · ruff.

En dev/tests se usa **SQLite** por defecto; en producción se inyecta `DATABASE_URL`
apuntando a PostgreSQL. El esquema se crea con `create_all` al arrancar (se migrará
a Alembic cuando el modelo se estabilice).

## Desarrollo

```bash
cd services/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"     # instala la app y las dependencias de desarrollo

.venv/bin/ruff check .                 # lint
.venv/bin/pytest -q                    # tests
.venv/bin/uvicorn app.main:app --reload   # servidor en http://127.0.0.1:8000
```

Docs interactivas (Swagger UI) en `http://127.0.0.1:8000/docs`.

### Estructura

```
app/
├── main.py       # App FastAPI, /health, montaje de routers, creación de tablas
├── config.py     # Settings (DATABASE_URL) desde entorno
├── database.py   # Engine, SessionLocal, Base, dependencia get_db
├── models.py     # Modelos SQLAlchemy (Supermercado, Producto)
├── schemas.py    # Esquemas Pydantic (Create/Update/Read)
└── routers/      # Endpoints CRUD por entidad
tests/            # pytest (BD SQLite en memoria, aislada por test)
```
