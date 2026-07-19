from decimal import Decimal

from app.parsing import parsear_lineas


def test_detecta_precio_con_coma():
    lineas = parsear_lineas("LECHE DESNATADA 0,89")
    assert len(lineas) == 1
    assert lineas[0].texto_original == "LECHE DESNATADA"
    assert lineas[0].precio_total == Decimal("0.89")


def test_detecta_precio_con_punto():
    lineas = parsear_lineas("PAN DE MOLDE 1.25")
    assert lineas[0].precio_total == Decimal("1.25")


def test_toma_el_ultimo_precio_de_la_linea():
    # "2 x 0,89   1,78" -> precio de la línea es el total (último)
    lineas = parsear_lineas("HUEVOS M 0,89 1,78")
    assert len(lineas) == 1
    assert lineas[0].precio_total == Decimal("1.78")


def test_ignora_lineas_de_resumen():
    texto = "LECHE 0,89\nTOTAL 0,89\nIVA 21% 0,15\nEFECTIVO 5,00"
    lineas = parsear_lineas(texto)
    assert len(lineas) == 1
    assert lineas[0].texto_original == "LECHE"


def test_no_confunde_iva_con_oliva():
    # "OLIVA" contiene "IVA": no debe descartarse como línea de resumen.
    lineas = parsear_lineas("ACEITE DE OLIVA 4,95")
    assert len(lineas) == 1
    assert lineas[0].texto_original == "ACEITE DE OLIVA"
    assert lineas[0].precio_total == Decimal("4.95")


def test_ignora_lineas_sin_precio():
    texto = "MERCADONA S.A.\nGRACIAS POR SU COMPRA\nLECHE 0,89"
    lineas = parsear_lineas(texto)
    assert len(lineas) == 1


def test_ignora_lineas_solo_numericas():
    lineas = parsear_lineas("5934 2025 12,00")
    assert lineas == []


def test_texto_vacio():
    assert parsear_lineas("") == []
