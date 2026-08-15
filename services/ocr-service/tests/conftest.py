import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def pdf(*paginas: list[str]) -> bytes:
    """Construye un PDF de verdad con las lineas de texto dadas, una lista por
    pagina.

    Escrito a mano (son unas pocas decenas de bytes) para no meter una
    dependencia de dev solo para generar el fichero de prueba, y para que los
    tests del camino "PDF con capa de texto" pasen por pypdf de verdad en vez
    de por un doble. Una pagina sin lineas es un PDF sin texto: justo lo que
    parece un escaneo, que es como se prueba la ruta del OCR.
    """
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,  # el arbol de paginas, que necesita saber los ids de sus hijas
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    hijas = []
    for lineas in paginas:
        flujo = (
            "BT /F1 12 Tf 40 760 Td 14 TL\n"
            + "".join(f"({texto}) Tj T*\n" for texto in lineas)
            + "ET"
        ).encode()
        objetos.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(flujo), flujo))
        id_flujo = len(objetos)
        objetos.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % id_flujo
        )
        hijas.append(len(objetos))
    objetos[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % hija for hija in hijas),
        len(hijas),
    )

    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n%s\nendobj\n" % (numero, objeto)
    inicio_xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for posicion in posiciones:
        salida += b"%010d 00000 n \n" % posicion
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objetos) + 1,
        inicio_xref,
    )
    return bytes(salida)
