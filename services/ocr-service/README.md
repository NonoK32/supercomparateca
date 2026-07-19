# ocr-service

Servicio de OCR en **Python + Tesseract**.

Recibe la imagen de un ticket y devuelve el texto extraído (líneas + precios).
Está aislado en su propio contenedor para poder sustituir el motor de OCR más
adelante sin tocar el resto del sistema.

La imagen **no se almacena**: se procesa y se descarta; solo se conserva el texto extraído.
