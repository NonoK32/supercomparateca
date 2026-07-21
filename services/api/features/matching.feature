# language: es
Característica: Reconocimiento automático de productos por similitud
  Como usuario que ya ha confirmado productos antes
  Quiero que el sistema reconozca textos parecidos del ticket
  Para no tener que confirmar lo mismo cada vez que el OCR escribe distinto

  Antecedentes:
    Dado que soy un usuario autenticado
    Y existe el supermercado "Mercadona"
    Y he confirmado que "LECHE DESNATADA" es el producto "Leche desnatada 1L"

  Escenario: Un texto casi idéntico se asocia solo
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNATAD 0,95
      """
    Entonces la primera línea del último ticket queda asociada a un producto
    Y el ticket queda en estado "procesado"

  Escenario: Un texto dudoso se sugiere en vez de asociarse solo
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      LECHE DESNAT 0,95
      """
    Entonces la primera línea del último ticket queda sin asociar
    Y el sistema sugiere el producto "Leche desnatada 1L" para la primera línea

  Escenario: Un texto sin parecido no se sugiere
    Cuando subo la foto de un ticket de "Mercadona" con el texto:
      """
      ATUN CLARO ACEITE 2,10
      """
    Entonces la primera línea del último ticket queda sin asociar
    Y el sistema no sugiere ningún producto para la primera línea
