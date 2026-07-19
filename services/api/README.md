# api

API REST y lógica de negocio en **Python (FastAPI)**.

Responsable de: modelos de datos, endpoints CRUD (productos, supermercados, tickets),
autenticación (JWT), asociación línea↔producto mediante alias y endpoints de
comparación de precios.

Se comunica con `ocr-service` por HTTP interno y con `db` (PostgreSQL) por SQL.
