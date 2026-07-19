from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class AsociarRequest(BaseModel):
    """Asocia una línea a un producto existente (`producto_id`) o crea/reutiliza
    uno nuevo (`nuevo_producto`). Debe indicarse exactamente uno de los dos."""

    producto_id: int | None = None
    nuevo_producto: ProductoCreate | None = None

    @model_validator(mode="after")
    def exactamente_uno(self):
        if (self.producto_id is None) == (self.nuevo_producto is None):
            raise ValueError(
                "Indica 'producto_id' o 'nuevo_producto' (exactamente uno)"
            )
        return self
