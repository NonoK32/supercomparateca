"""Deduce la fecha y el supermercado del texto OCR de un ticket.

Son dos datos que el ticket ya lleva impresos: pedírselos al usuario cuando
están ahí es hacerle transcribir. La heurística es deliberadamente conservadora
—ante la duda devuelve `None` y el `api` los pregunta—, porque colar una fecha o
un supermercado equivocados ensucia el histórico de precios sin que nadie se dé
cuenta, mientras que preguntar solo cuesta un formulario.

Como el resto del parseo, esto vive en el `api` y no en el `ocr-service`: es
lógica de negocio y se prueba sin Tesseract.
"""

import re
import unicodedata
from datetime import date, timedelta

# dd/mm/aaaa, dd-mm-aa, dd.mm.aaaa: el formato de aquí, día primero.
_FECHA_DIA_PRIMERO = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?!\d)")
# aaaa-mm-dd, que también aparece en tickets de caja modernos.
_FECHA_ISO = re.compile(r"(?<!\d)(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})(?!\d)")

# Un ticket que se está digitalizando es reciente. Más atrás de esto, lo que hay
# es un número mal leído (o la caducidad de una tarjeta), no una compra.
_ANTIGUEDAD_MAXIMA = timedelta(days=730)

# Solo se busca la marca en la cabecera: en un ticket español el nombre del
# comercio va arriba, y más abajo aparecen palabras que coinciden por accidente
# ("DIA" como abreviatura de fecha es el caso claro).
_LINEAS_CABECERA = 10


def _normalizar(texto: str) -> str:
    """Mayúsculas, sin tildes y sin puntuación: "Día, S.A." -> "DIA S A"."""
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^0-9A-Za-z]+", " ", sin_tildes).upper().strip()


def _a_fecha(dia: int, mes: int, anio: int) -> date | None:
    if anio < 100:
        anio += 2000
    try:
        return date(anio, mes, dia)
    except ValueError:
        # Descarta lo que no es una fecha: "12/28" (caducidad de tarjeta), un
        # 31 de febrero mal leído, etc.
        return None


def detectar_fecha(texto: str, hoy: date) -> date | None:
    """Primera fecha plausible del ticket, o `None`.

    `hoy` se pasa desde fuera porque el contenedor va en UTC y porque así la
    ventana de plausibilidad se puede probar sin depender del reloj.
    """
    candidatas: list[tuple[int, date]] = []
    for encontrado in _FECHA_DIA_PRIMERO.finditer(texto):
        dia, mes, anio = (int(g) for g in encontrado.groups())
        fecha = _a_fecha(dia, mes, anio)
        if fecha:
            candidatas.append((encontrado.start(), fecha))
    for encontrado in _FECHA_ISO.finditer(texto):
        anio, mes, dia = (int(g) for g in encontrado.groups())
        fecha = _a_fecha(dia, mes, anio)
        if fecha:
            candidatas.append((encontrado.start(), fecha))

    candidatas.sort()
    for _, fecha in candidatas:
        # Ni del futuro (eso es una caducidad o una promoción) ni de hace años.
        if hoy - _ANTIGUEDAD_MAXIMA <= fecha <= hoy:
            return fecha
    return None


def detectar_supermercado(
    texto: str, supermercados: list[tuple[int, str]]
) -> int | None:
    """Id del supermercado cuyo nombre aparece en la cabecera, o `None`.

    Solo compara contra los que ya existen: crear uno a partir de lo que diga el
    OCR llenaría el catálogo compartido de basura. Si sale uno nuevo, lo elige
    (o lo crea) el usuario.
    """
    cabecera = _normalizar("\n".join(texto.splitlines()[:_LINEAS_CABECERA]))
    mejor: tuple[int, int] | None = None  # (posición, id)
    for sm_id, nombre in supermercados:
        aguja = _normalizar(nombre)
        # Un nombre de una o dos letras coincidiría en cualquier parte.
        if len(aguja) < 3:
            continue
        encontrado = re.search(rf"\b{re.escape(aguja)}\b", cabecera)
        if encontrado and (mejor is None or encontrado.start() < mejor[0]):
            mejor = (encontrado.start(), sm_id)
    return mejor[1] if mejor else None
