"""Configuración de Behave: un cliente de API con BD SQLite en memoria y OCR
falso por escenario (mismo enfoque que los tests unitarios)."""

import os

# Debe fijarse antes de importar la app (config valida el secreto en el import).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-para-behave-1234567890abcdef")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, activar_fk_sqlite, get_db
from app.main import app
from app.ocr import get_ocr_client


class FakeOCR:
    texto = ""

    def extraer_texto(self, *args, **kwargs) -> str:
        return self.texto


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
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ocr_client] = lambda: context.fake_ocr

    context.client = TestClient(app)
    context.response = None
    context.ticket = None
    context.supermercados = {}


def after_scenario(context, scenario):
    app.dependency_overrides.clear()
