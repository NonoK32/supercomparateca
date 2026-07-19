# language: es
Característica: Comparación de precios
  Como usuario autenticado
  Quiero comparar el precio de un producto entre supermercados

  Antecedentes:
    Dado que soy un usuario autenticado
    Y existe el supermercado "Mercadona"
    Y existe el supermercado "Lidl"

  Escenario: El mismo producto es más barato en un supermercado
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNATADA 0,89
      """
    Y asocio la primera línea al producto nuevo "Leche desnatada 1L"
    Y subo la foto de un ticket de "Lidl" con el texto:
      """
      LECHE DESNATADA 1,05
      """
    Y asocio la primera línea al producto nuevo "Leche desnatada 1L"
    Entonces el producto "Leche desnatada 1L" cuesta menos en "Mercadona" que en "Lidl"
