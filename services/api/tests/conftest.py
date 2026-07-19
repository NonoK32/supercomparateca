import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.ocr import get_ocr_client


class FakeOCR:
    """OCR falso para tests: devuelve el texto que se le fije, sin red ni Tesseract."""

    texto = ""

    def extraer_texto(self, *args, **kwargs) -> str:
        return self.texto


@pytest.fixture
def fake_ocr():
    return FakeOCR()


@pytest.fixture
def client(fake_ocr):
    """Cliente de test con una BD SQLite en memoria (aislada por test) y OCR falso."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ocr_client] = lambda: fake_ocr
    # Sin context manager: no dispara el lifespan (que crearía la BD por defecto).
    yield TestClient(app)
    app.dependency_overrides.clear()
