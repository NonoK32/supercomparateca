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

# Desglose de un producto pesado: "0,532 kg x 2,49 EUR/kg". Lo que identifica a
# la línea es el precio POR UNIDAD —la barra—, no el peso: un producto puede
# llamarse "AGUA 1,5 L" pero ninguno lleva "€/kg" en el nombre.
_UNITARIO = re.compile(
    r"\d+[.,]\d+\s*(?:eur|€)?\s*/\s*(?:kg|gr|g|lt|l|ml|uds?|u)\b",
    re.IGNORECASE,
)

# Palabras de líneas de resumen del ticket que no son productos. Se comparan por
# palabra completa (no subcadena) para no descartar productos como "ACEITE DE
# OLIVA" (que contiene "IVA").
#
# La lista solo admite palabras que NINGÚN producto puede llevar en el nombre.
# Por eso no están "BASE" (existe la "BASE PIZZA" del Lidl) ni "PLUS": el coste
# de descartar un producto de verdad es mucho peor que el de colar una línea de
# resumen, que al menos se ve y se puede ignorar.
_IGNORAR = frozenset(
    {
        "TOTAL",
        "SUBTOTAL",
        "IVA",
        "EFECTIVO",
        "TARJETA",
        "CAMBIO",
        "ENTREGA",
        "DEVOLVER",
        # Promociones y descuentos (el "PROMO LIDL PLUS" del Lidl).
        "PROMO",
        "PROMOCION",
        "DESCUENTO",
        "DESCUENTOS",
        "DTO",
        "AHORRO",
        "AHORRAS",
        "CUPON",
        # Resumen de impuestos e importes: "BASE IMPONIBLE", "CUOTA IVA",
        # "Suma 5.30 69,10".
        "IMPONIBLE",
        "CUOTA",
        "SUMA",
        "IMPORTE",
        "REDONDEO",
    }
)

# Abreviaturas que solo delatan una línea de resumen cuando son TODA la
# descripción. Vistas en un ticket del Lidl como "DESC" e "IMP.:", pero
# descartarlas en cualquier posición se llevaría por delante productos reales:
# los tickets estrechos abrevian, y "CAFE DESC 250G" es un descafeinado, no un
# descuento. Igual "BASE": sola es la base imponible, acompañada es una BASE
# PIZZA.
_IGNORAR_SOLAS = frozenset({"DESC", "DCTO", "IMP", "IMPTE", "BASE"})

# Palabras de verdad de una descripción: 3+ letras seguidas. Sirve para
# distinguir un nombre de producto de una fila del resumen de impuestos.
_PALABRA = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


@dataclass
class LineaParseada:
    texto_original: str
    precio_total: Decimal


def _palabras(descripcion: str) -> set[str]:
    """Palabras en mayúsculas y sin puntuación pegada.

    El OCR ensucia los bordes ("TOTAL)", "*IVA."), así que comparar los trozos
    tal cual dejaba pasar justo las líneas que hay que descartar.
    """
    return {re.sub(r"[^0-9A-ZÁÉÍÓÚÜÑ]", "", p) for p in descripcion.upper().split()}


def _es_importe_negativo(cruda: str, precio: re.Match) -> bool:
    """¿El importe va en negativo? Entonces es un descuento o un abono.

    Es la señal más fiable que da un ticket —ningún producto cuesta -1,00— y no
    depende de cómo llame cada cadena a sus promociones. Hay que comprobarlo
    antes de recortar la descripción: el signo queda pegado al texto de la
    izquierda y el `strip` posterior se lo llevaría por delante.

    El signo detrás solo cuenta pegado al importe ("1,00-", como lo imprimen
    algunas cajas); suelto podría ser un guion cualquiera de la línea.
    """
    antes = cruda[: precio.start()].rstrip()
    return antes.endswith("-") or cruda[precio.end() :].startswith("-")


def _ultimo_precio(fragmento: str) -> Decimal | None:
    precios = list(_PRECIO.finditer(fragmento))
    if not precios:
        return None
    return Decimal(f"{precios[-1].group(1)}.{precios[-1].group(2)}")


def _es_tramo_de_impuestos(descripcion: str) -> bool:
    """Fila del resumen de impuestos del pie: "A 21%", "B 10%", "21 %".

    Llevan porcentaje y, como mucho, la letra del tipo impositivo. Basta con que
    quede una palabra de verdad (3+ letras) para considerarlo un producto, así
    que "YOGUR 0% MG" se salva.
    """
    return "%" in descripcion and not _PALABRA.search(descripcion)


def parsear_lineas(texto: str) -> list[LineaParseada]:
    lineas: list[LineaParseada] = []
    # Nombre de la línea anterior cuando venía sin importe. Los productos
    # pesados a veces se parten en dos: el nombre arriba y el total en la línea
    # del desglose por kilo.
    pendiente: str | None = None

    for cruda in texto.splitlines():
        cruda = cruda.strip()
        if not cruda:
            continue

        unitario = _UNITARIO.search(cruda)
        if unitario:
            # Es el desglose del producto anterior, nunca un producto. Si detrás
            # del precio por unidad viene otro importe, ese es el total de la
            # compra y el nombre está en la línea de arriba.
            total = _ultimo_precio(cruda[unitario.end() :])
            if total is not None and pendiente is not None:
                lineas.append(LineaParseada(texto_original=pendiente, precio_total=total))
            pendiente = None
            continue

        precios = list(_PRECIO.finditer(cruda))
        if not precios:
            # Sin importe puede ser el nombre de un producto pesado (el total
            # llegará en la siguiente línea) o ruido de cabecera; se recuerda
            # solo si parece un nombre.
            pendiente = cruda if any(c.isalpha() for c in cruda) else None
            continue

        pendiente = None
        ultimo = precios[-1]
        # Un importe en negativo es un descuento, no algo que se haya comprado.
        if _es_importe_negativo(cruda, ultimo):
            continue
        descripcion = cruda[: ultimo.start()].strip(" .-\t")

        # Debe quedar texto con letras (descarta líneas solo numéricas).
        if not any(c.isalpha() for c in descripcion):
            continue
        # Descarta líneas de resumen (TOTAL, IVA, etc.), por palabra completa.
        palabras = _palabras(descripcion)
        if _IGNORAR & palabras:
            continue
        if len(palabras) == 1 and palabras <= _IGNORAR_SOLAS:
            continue
        # Descarta el resumen de impuestos del pie ("A 21% 1,00 0,21 1,21").
        if _es_tramo_de_impuestos(descripcion):
            continue

        precio = Decimal(f"{ultimo.group(1)}.{ultimo.group(2)}")
        lineas.append(LineaParseada(texto_original=descripcion, precio_total=precio))
    return lineas
