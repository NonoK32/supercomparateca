FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instala las dependencias declaradas en pyproject (incluye psycopg para Postgres).
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Alembic: el entrypoint aplica las migraciones antes de arrancar uvicorn.
COPY alembic.ini ./
COPY migraciones ./migraciones
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Usuario no-root (NFR2).
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["./entrypoint.sh"]
