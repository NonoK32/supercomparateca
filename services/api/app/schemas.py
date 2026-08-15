from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


# ---- Usuario / Auth ----
class UsuarioCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    email: EmailStr
    # bcrypt usa como máximo los primeros 72 bytes de la contraseña.
    password: str = Field(min_length=8, max_length=72)
    # Token que genera el widget de Turnstile en el navegador. Opcional en el
    # esquema porque la verificación se desactiva si no hay clave secreta
    # configurada; cuando la hay, el router lo exige.
    turnstile_token: str | None = None


class AuthConfig(BaseModel):
    """Configuración pública que el frontend necesita antes de registrarse."""

    turnstile_site_key: str
    # Si el envío de correo NO está configurado, la verificación de email no
    # llega a nadie y nadie puede entrar. Se publica para que el smoke test lo
    # detecte tras cada despliegue, en vez de descubrirlo por un usuario que no
    # recibe nada. No revela ningún secreto: solo si el servicio está en pie.
    correo_activo: bool
    # Id de cliente OAuth de Google. Público por diseño (ver config.py). Vacío
    # = el frontend no pinta el botón.
    google_client_id: str = ""


class SolicitarCorreo(BaseModel):
    """Pedir que se reenvíe un correo (verificación o recuperación)."""

    email: EmailStr


class VerificarEmail(BaseModel):
    token: str


class AccesoGoogle(BaseModel):
    """El ID token que Google Identity Services entrega al navegador."""

    credential: str


class RestablecerPassword(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=72)


class BorrarCuenta(BaseModel):
    """Confirmación para el borrado de cuenta (art. 17 RGPD).

    Se pide la contraseña porque la acción es irreversible: un token robado no
    debería bastar para destruir la cuenta de alguien.
    """

    password: str


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    rol: str
    fecha_registro: datetime


class UsuarioAdminRead(UsuarioRead):
    """Lo que ve un admin en el panel.

    Añade si la cuenta llegó a confirmar el correo: sin confirmar no se puede
    entrar, así que son cuentas muertas y es lo primero que se quiere ver.
    """

    email_verificado: bool


class UsuarioUpdate(BaseModel):
    """Lo único que un admin cambia de la cuenta de otro es el rol.

    El nombre y el correo son de su dueño, y la contraseña no la puede saber
    nadie: para eso está la recuperación.
    """

    rol: Literal["usuario", "admin"]


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
    usuario_id: int | None
    supermercado_id: int
    fecha_compra: date
    estado: str
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


class ProductoCesta(BaseModel):
    producto_id: int
    nombre_normalizado: str
    veces_comprado: int


class TotalSupermercado(BaseModel):
    supermercado_id: int
    supermercado: str
    total: Decimal
    productos_cubiertos: int


class ComparativaCesta(BaseModel):
    """FR10: coste de la cesta habitual en cada supermercado. `productos_cubiertos`
    dice sobre cuántos de la cesta se ha podido calcular el total."""

    productos: list[ProductoCesta]
    supermercados: list[TotalSupermercado]


class ListaCompra(BaseModel):
    """Los productos que el usuario ha puesto en su lista.

    No se guarda en ninguna parte: la lista vive en el navegador y se manda
    entera para calcular. Una lista es cosa de un rato, y persistirla traería
    su propio CRUD y su borrado sin que nadie lo haya pedido.
    """

    producto_ids: list[int] = Field(min_length=1, max_length=50)


class ProductoLista(BaseModel):
    """Un producto de la lista con TODOS sus precios, de menor a mayor."""

    producto_id: int
    nombre_normalizado: str
    supermercados: list[PrecioSupermercado]


class ComparativaLista(BaseModel):
    productos: list[ProductoLista]
    supermercados: list[TotalSupermercado]


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
