# language: es
Característica: Ingesta de tickets
  Como usuario autenticado
  Quiero subir la foto de un ticket
  Para registrar mis compras y sus precios

  Antecedentes:
    Dado que soy un usuario autenticado
    Y existe el supermercado "Mercadona"

  Escenario: Subir un ticket de Mercadona y detectar productos
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNATADA 0,89
      PAN INTEGRAL 1,15
      TOTAL 2,04
      """
    Entonces el sistema extrae al menos 1 línea de producto con precio
    Y el ticket queda en estado "pendiente"

  Escenario: Un producto confirmado se reconoce en el siguiente ticket
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNATADA 0,89
      """
    Y asocio la primera línea al producto nuevo "Leche desnatada 1L"
    Y subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNATADA 0,95
      """
    Entonces la primera línea del último ticket queda asociada a un producto
