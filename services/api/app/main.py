from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, cesta, lineas, productos, supermercados, tickets

# El esquema NO se crea al arrancar: lo gestiona Alembic (`alembic upgrade
# head`, que el contenedor ejecuta en su entrypoint). Con `create_all` aquí, un
# cambio en models.py se aplicaba solo en bases de datos vacías y en producción
# quedaba callado: la tabla existente no se altera nunca.
app = FastAPI(title="SuperComparateca API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(supermercados.router)
app.include_router(productos.router)
app.include_router(tickets.router)
app.include_router(lineas.router)
app.include_router(cesta.router)
