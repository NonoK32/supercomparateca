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

    # Matching por similitud (§5bis punto 3). Por encima de `umbral_auto` se
    # asigna el producto sin preguntar; entre sugerencia y auto se propone al
    # usuario. Configurables porque hay que recalibrarlos con tickets reales
    # (y si algún día se cambia el motor de similitud).
    umbral_auto: float = 0.92
    umbral_sugerencia: float = 0.70

    @field_validator("jwt_secret_key")
    @classmethod
    def _secreto_seguro(cls, valor: str) -> str:
        if valor in _SECRETOS_INSEGUROS or len(valor) < 16:
            raise ValueError(
                "JWT_SECRET_KEY sin configurar o inseguro. "
                "Genera uno con: openssl rand -hex 32"
            )
        return valor

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
