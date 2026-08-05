"""Entorno de Alembic.

La URL sale de `app.config.settings` (es decir, de DATABASE_URL) y no de
alembic.ini: así el esquema se migra siempre contra la misma base de datos que
usa la app, sin credenciales en el repositorio.

Efecto secundario de importar la config: exige JWT_SECRET_KEY como cualquier
otro arranque de la app. Es el precio de tener una sola fuente de verdad para
la URL, y en los tres sitios donde se ejecuta alembic (contenedor, CI y
desarrollo) esa variable ya está definida.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

# Importa los modelos por su efecto secundario: registran sus tablas en
# Base.metadata, que es contra lo que comparan `alembic revision --autogenerate`
# y `alembic check`. Sin este import, autogenerate creería que hay que borrarlo
# todo.
from app import models  # noqa: F401
from app.config import settings
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a la base de datos (`alembic upgrade --sql`)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(settings.database_url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite no sabe hacer ALTER TABLE de casi nada: el modo batch
            # recrea la tabla. Necesario para que las migraciones futuras
            # corran también en dev, no solo en PostgreSQL.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
