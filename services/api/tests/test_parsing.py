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


def test_la_suciedad_del_ocr_no_salva_una_linea_de_resumen():
    # Visto en un ticket real: Tesseract lee "TOTAL 2,28" como "TOTAL) 2,28" y,
    # comparando palabras tal cual, "TOTAL)" ya no era "TOTAL" y el total se
    # colaba como si fuera un producto.
    assert parsear_lineas("TOTAL) 2,28") == []
    assert parsear_lineas("*IVA. 21% 0,15") == []


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


def test_el_desglose_por_kilo_no_es_un_producto():
    # Lidl (y la báscula de cualquier super): el importe va en la línea del
    # producto y el peso por su precio ocupa la siguiente. Sin esto aparecía un
    # producto fantasma «0,532 kg x» a 2,49 €.
    texto = "PLATANO 1,33\n0,532 kg x 2,49 EUR/kg"
    lineas = parsear_lineas(texto)
    assert len(lineas) == 1
    assert lineas[0].texto_original == "PLATANO"
    assert lineas[0].precio_total == Decimal("1.33")


def test_producto_pesado_partido_en_dos_lineas():
    # La otra variante: el nombre va solo y el total llega con el desglose. Aquí
    # el producto se perdía entero, porque su línea no tenía precio.
    texto = "TOMATE RAMA\n0,750 kg x 1,99 €/kg 1,49"
    lineas = parsear_lineas(texto)
    assert len(lineas) == 1
    assert lineas[0].texto_original == "TOMATE RAMA"
    assert lineas[0].precio_total == Decimal("1.49")


def test_desglose_sin_producto_delante_no_inventa_nada():
    assert parsear_lineas("0,532 kg x 2,49 EUR/kg") == []


def test_ignora_los_tramos_de_impuestos():
    # El resumen de impuestos del pie del ticket: una fila por tipo. La letra
    # suelta colaba como nombre de producto.
    texto = "LECHE 0,89\nA 21% 1,00 0,21 1,21\nB 10% 2,00 0,20 2,20"
    lineas = parsear_lineas(texto)
    assert len(lineas) == 1
    assert lineas[0].texto_original == "LECHE"


def test_ignora_promociones_descuentos_y_resumenes():
    # Todo esto salió como producto en un ticket real del Lidl.
    texto = (
        "PROMO LIDL PLUS 2,00\n"
        "BASE IMPONIBLE 10,00\n"
        "CUOTA IVA 1,00\n"
        "SUMA 12,10\n"
        "DESCUENTO 1,00\n"
        "LECHE ENTERA 0,95"
    )
    lineas = parsear_lineas(texto)
    assert [linea.texto_original for linea in lineas] == ["LECHE ENTERA"]


def test_las_cuatro_lineas_que_se_colaron_en_un_ticket_real():
    # Textos tal cual los guardó la app de un ticket del Lidl.
    texto = 'Suma 5.30 69,10\nIMP.: 12,34\nPROMO LIDL PLUS 2,00\nDESC 1,00'
    assert parsear_lineas(texto) == []


def test_las_abreviaturas_solo_cuentan_si_van_solas():
    # "DESC" a secas es un descuento; dentro de un nombre es un descafeinado.
    lineas = parsear_lineas("CAFE DESC 250G 2,50")
    assert len(lineas) == 1
    assert lineas[0].texto_original == "CAFE DESC 250G"


def test_un_importe_negativo_nunca_es_un_producto():
    # La señal más fiable, y no depende de cómo llame cada cadena a su promoción.
    assert parsear_lineas("AHORRO EN ESTA COMPRA -1,00") == []
    assert parsear_lineas("Cheque bienvenida 0,50-") == []


def test_el_descuento_no_se_lleva_por_delante_el_producto_de_arriba():
    texto = "PLATANO 1,33\nDto. promocion -0,20"
    lineas = parsear_lineas(texto)
    assert len(lineas) == 1
    assert lineas[0].texto_original == "PLATANO"
    assert lineas[0].precio_total == Decimal("1.33")


def test_un_producto_con_guion_en_el_nombre_se_conserva():
    # "COLA-CAO" acaba en algo parecido a un signo, pero el guion va pegado a la
    # palabra, no al importe.
    lineas = parsear_lineas("COLA-CAO 2,50")
    assert len(lineas) == 1
    assert lineas[0].precio_total == Decimal("2.50")


def test_no_descarta_productos_que_llevan_base_en_el_nombre():
    # El Lidl vende "BASE PIZZA": por eso "BASE" no está en la lista y sí
    # "IMPONIBLE".
    lineas = parsear_lineas("BASE PIZZA 1,29")
    assert len(lineas) == 1
    assert lineas[0].texto_original == "BASE PIZZA"


def test_un_porcentaje_en_el_nombre_no_lo_convierte_en_tramo():
    # "YOGUR 0% MG" lleva porcentaje y sigue siendo un producto: lo que delata
    # al tramo de impuestos es que no queda ninguna palabra de verdad.
    lineas = parsear_lineas("YOGUR 0% MG 1,15")
    assert len(lineas) == 1
    assert lineas[0].texto_original == "YOGUR 0% MG"


def test_texto_vacio():
    assert parsear_lineas("") == []
