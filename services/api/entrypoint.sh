#!/bin/sh
# Migra el esquema y arranca la API.
#
# `upgrade head` es idempotente: si la base de datos ya está al día no hace
# nada. Si falla, `set -e` aborta el arranque a propósito — es preferible que el
# contenedor no levante a que sirva peticiones contra un esquema desfasado.
set -e

echo "Aplicando migraciones (alembic upgrade head)..."
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
