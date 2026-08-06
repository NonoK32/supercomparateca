from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # "usuario" | "admin". Solo admin puede modificar/borrar los datos globales
    # (productos, supermercados) de los que dependen todos los demás.
    rol: Mapped[str] = mapped_column(String(20), default="usuario")
    # Sin verificar no se puede iniciar sesión: es lo que hace que la
    # verificación signifique algo y garantiza que toda cuenta tenga un correo
    # real al que mandar la recuperación de contraseña. Los usuarios que ya
    # existían cuando se añadió esto quedaron verificados en la migración.
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable a propósito: al borrar su cuenta, un usuario deja los tickets
    # huérfanos en vez de eliminarlos. Los precios son un bien compartido y
    # borrarlos degradaría la comparativa de todos; sin dueño ya no son datos
    # personales, y `_ticket_propio` deja de dar acceso a nadie.
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), default=None
    )
    supermercado_id: Mapped[int] = mapped_column(ForeignKey("supermercados.id"))
    fecha_compra: Mapped[date] = mapped_column(Date)
    # NO se guarda el texto OCR completo. La imagen se descarta tras el OCR y
    # el texto tampoco se persiste: un ticket real lleva los 4 últimos dígitos
    # de la tarjeta, el número de fidelización, la hora exacta y la caja. Solo
    # sobreviven las líneas parseadas (LineaTicket), que es lo que la app usa.
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")

    lineas: Mapped[list["LineaTicket"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class LineaTicket(Base):
    __tablename__ = "lineas_ticket"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    texto_original: Mapped[str] = mapped_column(String(300))
    cantidad: Mapped[int] = mapped_column(default=1)
    precio_unitario: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    precio_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    producto_id: Mapped[int | None] = mapped_column(
        ForeignKey("productos.id"), default=None
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="lineas")


class AliasProducto(Base):
    """Aprendizaje: qué producto corresponde a un texto de ticket, por supermercado.

    El aprendizaje es compartido entre usuarios (Fase 3), pero cada uno puede
    discrepar: un alias pertenece a quien lo confirmó (`usuario_id`) y, al
    resolver un texto, el alias propio gana sobre el de la comunidad. Así la
    corrección de un usuario no le pisa el producto a los demás.

    `usuario_id` es nullable para admitir alias sin dueño (datos heredados o
    sembrados). La unicidad es por usuario: dos personas pueden mapear el mismo
    texto a productos distintos.
    """

    __tablename__ = "alias_producto"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id", "supermercado_id", "texto_alias", name="uq_alias_sm_texto"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    supermercado_id: Mapped[int] = mapped_column(ForeignKey("supermercados.id"))
    texto_alias: Mapped[str] = mapped_column(String(300), index=True)
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), default=None
    )
