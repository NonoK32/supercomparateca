from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores que NUNCA deben usarse como secreto en un despliegue real. Si se
# detecta uno de ellos (o algo demasiado corto), la app se niega a arrancar.
_SECRETOS_INSEGUROS = {
    "",
    "dev-insecure-secret-change-me-in-production",
    "cambia-esto-por-un-secreto-largo-y-aleatorio",
}


class Settings(BaseSettings):
    """Configuración de la API, leída de variables de entorno.

    En desarrollo/tests se usa SQLite por defecto; en producción se inyecta
    DATABASE_URL apuntando a PostgreSQL (ver .env.example).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./supercomparateca.db"
    ocr_service_url: str = "http://ocr-service:8001"

    # Obligatorio: no hay valor por defecto usable. Genera uno con:
    #   openssl rand -hex 32
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Orígenes permitidos para el frontend (CORS), separados por comas.
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080"

    # Turnstile (anti-bot de Cloudflare) en el registro. La clave de sitio es
    # pública: el frontend la pide en GET /auth/config, así no hay que
    # recompilar nada al cambiarla. La secreta NO sale del servidor.
    #
    # Si turnstile_secret_key está vacía la verificación se desactiva, para que
    # el desarrollo y los tests no necesiten credenciales de Cloudflare. En
    # producción hay que definirla: sin ella el registro queda abierto.
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""

    # Correo transaccional (Resend): verificación de email y recuperación de
    # contraseña. Sin `resend_api_key` no se envía nada y los mensajes van al
    # log (ver correo.py), que es lo cómodo en desarrollo.
    resend_api_key: str = ""
    # El dominio del remitente tiene que estar verificado en Resend, con sus
    # registros SPF/DKIM en el DNS, o los correos se rechazan o van a spam.
    correo_remitente: str = "SuperComparateca <no-reply@supercomparateca.com>"
    # Base de los enlaces que se mandan por correo. Apunta al FRONTEND, no a la
    # api: quien abre el enlace es una persona con un navegador.
    frontend_url: str = "http://localhost:8090"

    # Caducidad de los enlaces enviados por correo. La verificación es larga
    # (la gente no mira el correo al momento); el restablecimiento es corto
    # porque da acceso a la cuenta a quien tenga el enlace.
    verificacion_expira_horas: int = 24
    reset_expira_minutos: int = 60

    # Matching por similitud (§5bis punto 3). Por encima de `umbral_auto` se
    # asigna el producto sin preguntar; entre sugerencia y auto se propone al
    # usuario. Configurables porque hay que recalibrarlos con tickets reales
    # (y si algún día se cambia el motor de similitud).
    umbral_auto: float = 0.92
    umbral_sugerencia: float = 0.70

    @field_validator("jwt_secret_key")
    @classmethod
    def _secreto_seguro(cls, valor: str) -> str:
        # 32 caracteres minimo: HS256 firma con el secreto en claro, asi que uno
        # corto es vulnerable a fuerza bruta offline sobre un token capturado.
        # `openssl rand -hex 32` da 64, que es lo que documentamos.
        if valor in _SECRETOS_INSEGUROS or len(valor) < 32:
            raise ValueError(
                "JWT_SECRET_KEY sin configurar o inseguro. "
                "Genera uno con: openssl rand -hex 32"
            )
        return valor

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
