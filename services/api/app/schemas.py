from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# ---- Usuario / Auth ----
class UsuarioCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    email: EmailStr
    # bcrypt usa como máximo los primeros 72 bytes de la contraseña.
    password: str = Field(min_length=8, max_length=72)


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    fecha_registro: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
    usuario_id: int
    supermercado_id: int
    fecha_compra: date
    estado: str
    texto_ocr_bruto: str
    lineas: list[LineaTicketRead]


# ---- Consultas de precios ----
class PrecioSupermercado(BaseModel):
    supermercado_id: int
    supermercado: str
    precio_actual: Decimal
    fecha: date
    num_observaciones: int


class ComparativaPrecios(BaseModel):
    producto_id: int
    nombre_normalizado: str
    supermercados: list[PrecioSupermercado]


class PuntoHistorico(BaseModel):
    fecha: date
    precio: Decimal
    supermercado_id: int
    supermercado: str


class HistoricoPrecios(BaseModel):
    producto_id: int
    historico: list[PuntoHistorico]


class SugerenciaProducto(BaseModel):
    """Producto propuesto para una línea sin asociar (§5bis punto 3)."""

    producto_id: int
    nombre_normalizado: str
    texto_alias: str
    score: float


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
