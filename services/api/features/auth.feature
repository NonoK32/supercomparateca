# language: es
Característica: Autenticación
  Para proteger los datos, la API exige iniciar sesión

  Escenario: Un endpoint protegido rechaza peticiones sin token
    Cuando pido la lista de supermercados sin autenticarme
    Entonces la respuesta es 401

  Escenario: Registro e inicio de sesión
    Dado que me registro con email "nuevo@example.com" y contraseña "password123"
    Cuando inicio sesión con email "nuevo@example.com" y contraseña "password123"
    Entonces recibo un token de acceso
