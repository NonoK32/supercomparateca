from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Supermercado(Base):
    __tablename__ = "supermercados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_normalizado: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    categoria: Mapped[str | None] = mapped_column(String(100), default=None)
    unidad_medida: Mapped[str | None] = mapped_column(String(50), default=None)
