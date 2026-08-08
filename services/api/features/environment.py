"""Configuración de Behave: un cliente de API con BD SQLite en memoria y OCR
falso por escenario (mismo enfoque que los tests unitarios)."""

import os

# Debe fijarse antes de importar la app (config valida el secreto en el import).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-para-behave-1234567890abcdef")

import re

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.correo import get_cliente_correo
from app.database import Base, activar_fk_sqlite, get_db
from app.main import app
from app.ocr import get_ocr_client


class FakeOCR:
    texto = ""

    def extraer_texto(self, *args, **kwargs) -> str:
        return self.texto


class FakeCorreo:
    """Buzón en memoria, como el de los tests unitarios."""

    def __init__(self):
        self.enviados = []

    @property
    def activo(self) -> bool:
        return True

    def enviar(self, destinatario, asunto, html, texto):
        self.enviados.append(
            {"para": destinatario, "asunto": asunto, "html": html, "texto": texto}
        )

    def token(self, clave="verificar"):
        if not self.enviados:
            return None
        encontrado = re.search(rf"{clave}=([\w.\-]+)", self.enviados[-1]["html"])
        return encontrado.group(1) if encontrado else None


def before_scenario(context, scenario):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    activar_fk_sqlite(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    context.fake_ocr = FakeOCR()
    context.fake_correo = FakeCorreo()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ocr_client] = lambda: context.fake_ocr
    app.dependency_overrides[get_cliente_correo] = lambda: context.fake_correo

    context.client = TestClient(app)
    # El buzón, colgado del cliente: los pasos que dan de alta un usuario lo
    # necesitan para confirmar el correo, que ahora es obligatorio para entrar.
    context.client.correo = context.fake_correo
    context.response = None
    context.ticket = None
    context.supermercados = {}


def after_scenario(context, scenario):
    app.dependency_overrides.clear()
