from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import Base, engine
from .routers import auth, lineas, productos, supermercados, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas al arrancar. Se sustituirá por Alembic cuando el modelo
    # se estabilice.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="SuperComparateca API", version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(supermercados.router)
app.include_router(productos.router)
app.include_router(tickets.router)
app.include_router(lineas.router)
