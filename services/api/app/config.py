from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la API, leída de variables de entorno.

    En desarrollo/tests se usa SQLite por defecto; en producción se inyecta
    DATABASE_URL apuntando a PostgreSQL (ver .env.example).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./supercomparateca.db"
    ocr_service_url: str = "http://ocr-service:8001"

    # Secreto JWT: en producción se inyecta por entorno (nunca el valor por
    # defecto). Genera uno con: openssl rand -hex 32
    jwt_secret_key: str = "dev-insecure-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


settings = Settings()
