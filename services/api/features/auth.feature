# language: es
Característica: Autenticación
  Para proteger los datos, la API exige iniciar sesión

  Escenario: Un endpoint protegido rechaza peticiones sin token
    Cuando pido la lista de supermercados sin autenticarme
    Entonces la respuesta es 401

  Escenario: Registro, confirmación del correo e inicio de sesión
    Dado que me registro con email "nuevo@example.com" y contraseña "password123"
    Y confirmo mi correo desde el enlace que me llega
    Cuando inicio sesión con email "nuevo@example.com" y contraseña "password123"
    Entonces recibo un token de acceso

  Escenario: Sin confirmar el correo no se puede entrar
    Dado que me registro con email "nuevo@example.com" y contraseña "password123"
    Cuando inicio sesión con email "nuevo@example.com" y contraseña "password123"
    Entonces la respuesta es 403

  Escenario: Recuperar la contraseña olvidada
    Dado que me registro con email "nuevo@example.com" y contraseña "password123"
    Y confirmo mi correo desde el enlace que me llega
    Cuando pido recuperar la contraseña de "nuevo@example.com"
    Y elijo la contraseña nueva "otra-password-9" desde el enlace que me llega
    Y inicio sesión con email "nuevo@example.com" y contraseña "otra-password-9"
    Entonces recibo un token de acceso
