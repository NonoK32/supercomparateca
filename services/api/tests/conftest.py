import os
import re

# Secreto JWT para los tests: debe fijarse antes de importar la app (config lo
# exige y lo valida en el import).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-para-tests-1234567890abcdef")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.correo import ErrorCorreo, get_cliente_correo
from app.database import Base, activar_fk_sqlite, get_db
from app.google_auth import ErrorGoogle, IdentidadGoogle, get_verificador_google
from app.main import app
from app.ocr import get_ocr_client


class FakeOCR:
    """OCR falso para tests: devuelve el texto que se le fije, sin red ni Tesseract.

    `error` simula que el ocr-service no ha sabido abrir el archivo, que con los
    PDF deja de ser rebuscado (uno con contraseña, uno a medio descargar).
    """

    texto = ""
    error: Exception | None = None

    def __init__(self):
        # Un texto por archivo, para los tickets subidos en varias capturas. Si
        # está vacía se devuelve `texto` en cada llamada, que es lo que espera
        # casi todo test.
        self.paginas = []

    def extraer_texto(self, *args, **kwargs) -> str:
        if self.error is not None:
            raise self.error
        return self.paginas.pop(0) if self.paginas else self.texto


class FakeCorreo:
    """Buzón en memoria: guarda los mensajes en vez de enviarlos.

    `fallar` permite simular que el proveedor está caído, que es un camino con
    consecuencias reales (el registro se deshace).
    """

    def __init__(self):
        self.enviados = []
        self.fallar = False

    @property
    def activo(self) -> bool:
        return True

    def enviar(self, destinatario, asunto, html, texto):
        if self.fallar:
            raise ErrorCorreo("proveedor caído (simulado)")
        self.enviados.append(
            {"para": destinatario, "asunto": asunto, "html": html, "texto": texto}
        )

    def token(self, clave="verificar"):
        """Saca el token del último enlace enviado (`verificar` o `restablecer`)."""
        if not self.enviados:
            return None
        encontrado = re.search(rf"{clave}=([\w.\-]+)", self.enviados[-1]["html"])
        return encontrado.group(1) if encontrado else None


class FakeGoogle:
    """Verificador de Google falso: ni red ni credenciales.

    Por defecto está activo y acredita `identidad`; `fallar` simula un token que
    Google no valida (caducado, de otra aplicación o con el correo sin
    confirmar), que es el camino que no debe dejar entrar a nadie.
    """

    def __init__(self):
        self.activo = True
        self.fallar = False
        self.identidad = IdentidadGoogle(email="ana@gmail.com", nombre="Ana")

    def verificar(self, credencial):
        if self.fallar:
            raise ErrorGoogle("token no válido (simulado)")
        return self.identidad


@pytest.fixture
def fake_google():
    return FakeGoogle()


@pytest.fixture
def fake_ocr():
    return FakeOCR()


@pytest.fixture
def fake_correo():
    return FakeCorreo()


@pytest.fixture
def api_client(fake_ocr, fake_correo, fake_google):
    """Cliente base con BD SQLite en memoria (aislada por test) y OCR falso.
    Sin autenticar: útil para probar registro/login y respuestas 401."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    activar_fk_sqlite(engine)
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
    app.dependency_overrides[get_cliente_correo] = lambda: fake_correo
    app.dependency_overrides[get_verificador_google] = lambda: fake_google
    # Sin context manager: no dispara el lifespan (que crearía la BD por defecto).
    cliente = TestClient(app)
    # El buzón viaja colgado del cliente para que los ayudantes lo alcancen sin
    # que cada test tenga que pasarlo a mano.
    cliente.correo = fake_correo
    cliente.google = fake_google
    yield cliente
    app.dependency_overrides.clear()


def registrar_y_login(cliente, email="test@example.com", password="password123"):
    """Registra un usuario, confirma su correo e inicia sesión.

    La confirmación va por el camino real: se saca el token del enlace del
    mensaje que ha quedado en el buzón falso (colgado del cliente). Así cada
    test que necesita un usuario ejercita de paso el flujo de verificación, en
    vez de saltárselo tocando la base de datos.
    """
    cliente.post(
        "/auth/registro",
        json={"nombre": "Test", "email": email, "password": password},
    )
    buzon = getattr(cliente, "correo", None)
    if buzon is not None and (token := buzon.token("verificar")):
        cliente.post("/auth/verificar", json={"token": token})

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
