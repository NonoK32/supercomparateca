from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# SQLite necesita check_same_thread=False para usarse desde el pool de FastAPI.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def activar_fk_sqlite(motor) -> None:
    """SQLite no comprueba las claves foráneas por defecto; lo activamos para que
    dev/tests se comporten como PostgreSQL (borrados de entidades en uso fallan)."""

    @event.listens_for(motor, "connect")
    def _pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


if settings.database_url.startswith("sqlite"):
    activar_fk_sqlite(engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependencia de FastAPI: abre una sesión por petición y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
