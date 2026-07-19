"""Parseo heurístico del texto OCR de un ticket en líneas de producto + precio.

Es deliberadamente simple (MVP): detecta el precio como un número con dos
decimales al final de la línea y toma el texto previo como descripción. No
intenta separar cantidad ni precio unitario (eso queda para más adelante).
"""

import re
from dataclasses import dataclass
from decimal import Decimal

# Precio: 1 a 4 dígitos, coma o punto decimal, exactamente 2 decimales.
_PRECIO = re.compile(r"(?<!\d)(\d{1,4})[.,](\d{2})(?!\d)")

# Líneas de resumen del ticket que no son productos.
_IGNORAR = (
    "TOTAL",
    "SUBTOTAL",
    "IVA",
    "EFECTIVO",
    "TARJETA",
    "CAMBIO",
    "ENTREGA",
    "DEVOLVER",
)


@dataclass
class LineaParseada:
    texto_original: str
    precio_total: Decimal


def parsear_lineas(texto: str) -> list[LineaParseada]:
    lineas: list[LineaParseada] = []
    for cruda in texto.splitlines():
        cruda = cruda.strip()
        if not cruda:
            continue

        precios = list(_PRECIO.finditer(cruda))
        if not precios:
            continue

        ultimo = precios[-1]
        descripcion = cruda[: ultimo.start()].strip(" .-\t")

        # Debe quedar texto con letras (descarta líneas solo numéricas).
        if not any(c.isalpha() for c in descripcion):
            continue
        # Descarta líneas de resumen (TOTAL, IVA, etc.).
        if any(palabra in descripcion.upper() for palabra in _IGNORAR):
            continue

        precio = Decimal(f"{ultimo.group(1)}.{ultimo.group(2)}")
        lineas.append(LineaParseada(texto_original=descripcion, precio_total=precio))
    return lineas
