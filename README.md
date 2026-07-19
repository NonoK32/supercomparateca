# SuperComparateca

App para **comparar precios de la compra** entre supermercados españoles (Mercadona, Lidl, Dia, Aldi) a partir de tickets escaneados.

Subes la foto de un ticket, el sistema extrae el texto por OCR, confirmas a qué producto corresponde cada línea y queda guardado con precio, fecha y supermercado. Después puedes consultar el histórico y comparar precios entre supermercados y en el tiempo.

> Proyecto en desarrollo. La especificación completa está en [`Docs/spec-comparador-precios.md`](Docs/spec-comparador-precios.md).

## Arquitectura

Sistema multicontenedor (Docker), cada servicio aislado:

| Servicio | Tecnología | Responsabilidad |
|---|---|---|
| `api` | Python (FastAPI) | Endpoints REST y lógica de negocio |
| `ocr-service` | Python + Tesseract | Extracción de texto de las imágenes de tickets |
| `db` | PostgreSQL | Persistencia |
| `reverse-proxy` | Nginx / Traefik | HTTPS (Let's Encrypt) |
| `frontend` | Web simple | Subir tickets, confirmar productos, ver comparativas |

Comunicación: `api ↔ ocr-service` por HTTP interno; `api ↔ db` por SQL.

## Estructura del repositorio

```
.
├── Docs/          # Especificación y documentación
├── services/
│   ├── api/           # API REST + lógica de negocio
│   ├── ocr-service/   # OCR con Tesseract
│   └── frontend/      # Interfaz web
└── infra/
    └── ansible/       # Aprovisionamiento del servidor (IaC)
```

## Puesta en marcha (Docker)

```bash
cp .env.example .env        # y rellena los valores reales
docker compose up --build   # levanta db (PostgreSQL), ocr-service y api
```

- API en `http://localhost:8000` (Swagger en `/docs`).
- `db` y `ocr-service` quedan en la red interna (sin puertos al host).
- La imagen del `ocr-service` incluye Tesseract con español.

El archivo `.env` está en `.gitignore` y **nunca** debe subirse al repositorio.

Para desarrollar un servicio suelto (sin Docker), mira su `README.md`
(`services/api`, `services/ocr-service`); en ese modo el `api` usa SQLite.

## Roadmap (fases)

- **MVP (Fase 1):** un usuario; asociación manual línea↔producto; histórico y comparativa; frontend simple.
- **Fase 2:** matching automático de productos por similitud de texto.
- **Fase 3:** multiusuario con datos de precios compartidos y seguridad completa.
- **Fase 4 (opcional):** migración a k3s.

## Convenciones de commits

Se sigue [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(<ámbito opcional>): <descripción en imperativo>
```

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `build`.

Ejemplos:

```
feat(api): añadir endpoint de comparación de precios
fix(ocr): corregir extracción de precios con coma decimal
docs: documentar el mecanismo de alias
```

## Seguridad

- Secretos siempre fuera del código (variables de entorno / variables de CI).
- Contraseñas hasheadas con bcrypt; sesiones con JWT; HTTPS end-to-end.
- Las imágenes de los tickets **no se almacenan**: se descartan tras el OCR y solo se guarda el texto extraído.
