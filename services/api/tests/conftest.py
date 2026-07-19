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
def api_client(fake_ocr):
    """Cliente base con BD SQLite en memoria (aislada por test) y OCR falso.
    Sin autenticar: útil para probar registro/login y respuestas 401."""
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


def registrar_y_login(cliente, email="test@example.com", password="password123"):
    """Registra un usuario e inicia sesión; devuelve el token de acceso."""
    cliente.post(
        "/auth/registro",
        json={"nombre": "Test", "email": email, "password": password},
    )
    resp = cliente.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return resp.json()["access_token"]


@pytest.fixture
def client(api_client):
    """Cliente autenticado (usuario por defecto). Lo usan la mayoría de tests."""
    token = registrar_y_login(api_client)
    api_client.headers["Authorization"] = f"Bearer {token}"
    return api_client
