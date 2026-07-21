# language: es
Característica: Multiusuario con datos de precios compartidos
  Como grupo de amigos que compramos en los mismos supermercados
  Queremos compartir los precios de nuestros tickets
  Para que la comparativa sea más fiable, sin que nadie pise los datos de otro

  Antecedentes:
    Dado que soy un usuario autenticado
    Y existe el supermercado "Mercadona"
    Y existe el supermercado "Lidl"

  Escenario: El ticket de otro usuario mejora mi comparativa
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNATADA 0,89
      """
    Y asocio la primera línea al producto nuevo "Leche desnatada 1L"
    Y entra otro usuario "bea@example.com"
    Y subo la foto de un ticket de "Lidl" con el texto:
      """
      LECHE DESNATADA 0,75
      """
    Y asocio la primera línea al producto existente "Leche desnatada 1L"
    Entonces el producto "Leche desnatada 1L" cuesta menos en "Lidl" que en "Mercadona"

  Escenario: Un usuario normal no puede borrar el catálogo compartido
    Cuando entra otro usuario "bea@example.com"
    Y intento borrar el supermercado "Mercadona"
    Entonces la respuesta es 403

  Escenario: Comparar el coste de mi cesta habitual
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNATADA 0,89
      """
    Y asocio la primera línea al producto nuevo "Leche desnatada 1L"
    Y subo la foto de un ticket de "Lidl" con el texto:
      """
      LECHE DESNATADA 0,75
      """
    Y asocio la primera línea al producto existente "Leche desnatada 1L"
    Y consulto la comparativa de mi cesta habitual
    Entonces mi cesta habitual incluye "Leche desnatada 1L"
    Y la cesta sale más barata en "Lidl"
