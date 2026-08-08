from datetime import date

from app.deteccion import detectar_fecha, detectar_supermercado

HOY = date(2026, 8, 7)

SUPERS = [(1, "Mercadona"), (2, "Lidl"), (3, "Dia"), (4, "Aldi")]


# ---- Fecha ----


def test_detecta_fecha_dia_primero():
    assert detectar_fecha("MERCADONA\n05/08/2026 13:42\nLECHE 0,89", HOY) == date(
        2026, 8, 5
    )


def test_acepta_los_separadores_habituales():
    assert detectar_fecha("05-08-2026", HOY) == date(2026, 8, 5)
    assert detectar_fecha("05.08.2026", HOY) == date(2026, 8, 5)


def test_acepta_el_ano_de_dos_cifras():
    assert detectar_fecha("05/08/26", HOY) == date(2026, 8, 5)


def test_detecta_fecha_en_formato_iso():
    assert detectar_fecha("FECHA 2026-08-05", HOY) == date(2026, 8, 5)


def test_ignora_lo_que_no_es_una_fecha():
    # "12/28" es la caducidad de la tarjeta: no hay mes 28.
    assert detectar_fecha("CADUCA 12/28", HOY) is None


def test_ignora_fechas_futuras():
    # Una fecha por delante de hoy es una promoción o una caducidad.
    assert detectar_fecha("VALIDO HASTA 31/12/2027", HOY) is None


def test_ignora_fechas_demasiado_viejas():
    assert detectar_fecha("01/01/2019", HOY) is None


def test_se_queda_con_la_primera_plausible():
    # La caducidad va delante pero no es válida; gana la compra.
    texto = "CADUCA 12/28\nCOMPRA 05/08/2026"
    assert detectar_fecha(texto, HOY) == date(2026, 8, 5)


def test_sin_fecha_devuelve_none():
    assert detectar_fecha("LECHE DESNATADA 0,89", HOY) is None


# ---- Supermercado ----


def test_detecta_el_supermercado_de_la_cabecera():
    texto = "MERCADONA S.A.\nC/ MAYOR 3\nLECHE 0,89"
    assert detectar_supermercado(texto, SUPERS) == 1


def test_detecta_sin_importar_tildes_ni_mayusculas():
    assert detectar_supermercado("Supermercados Día, S.A.", SUPERS) == 3


def test_no_confunde_dia_de_fecha_con_el_supermercado_dia():
    # "DIA" aparece a menudo como abreviatura de fecha, pero fuera de la
    # cabecera: por eso solo se mira arriba.
    texto = "\n".join(["MERCADONA S.A.", "C/ MAYOR 3"] + ["LECHE 0,89"] * 12 + ["DIA 05/08/2026"])
    assert detectar_supermercado(texto, SUPERS) == 1


def test_supermercado_desconocido_no_se_inventa():
    assert detectar_supermercado("CARREFOUR EXPRESS\nPAN 1,00", SUPERS) is None


def test_gana_el_que_aparece_antes():
    texto = "LIDL SUPERMERCADOS\nCOMPARA CON MERCADONA"
    assert detectar_supermercado(texto, SUPERS) == 2


def test_no_coincide_dentro_de_otra_palabra():
    # "ALDI" dentro de "ALDIA" no es el supermercado.
    assert detectar_supermercado("SUPER ALDIA\nPAN 1,00", SUPERS) is None
