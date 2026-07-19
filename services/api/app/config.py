from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la API, leída de variables de entorno.

    En desarrollo/tests se usa SQLite por defecto; en producción se inyecta
    DATABASE_URL apuntando a PostgreSQL (ver .env.example).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./supercomparateca.db"
    ocr_service_url: str = "http://ocr-service:8001"


settings = Settings()
