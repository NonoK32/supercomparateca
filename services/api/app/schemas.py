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
