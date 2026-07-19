from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ---- Supermercado ----
class SupermercadoBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)


class SupermercadoCreate(SupermercadoBase):
    pass


class SupermercadoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)


class SupermercadoRead(SupermercadoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---- Producto ----
class ProductoBase(BaseModel):
    nombre_normalizado: str = Field(min_length=1, max_length=200)
    categoria: str | None = Field(default=None, max_length=100)
    unidad_medida: str | None = Field(default=None, max_length=50)


class ProductoCreate(ProductoBase):
    pass


class ProductoUpdate(BaseModel):
    nombre_normalizado: str | None = Field(default=None, min_length=1, max_length=200)
    categoria: str | None = Field(default=None, max_length=100)
    unidad_medida: str | None = Field(default=None, max_length=50)


class ProductoRead(ProductoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---- Ticket / LineaTicket ----
class LineaTicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    texto_original: str
    cantidad: int
    precio_unitario: Decimal | None
    precio_total: Decimal
    producto_id: int | None


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supermercado_id: int
    fecha_compra: date
    estado: str
    texto_ocr_bruto: str
    lineas: list[LineaTicketRead]
