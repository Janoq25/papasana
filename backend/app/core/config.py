from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (ver .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PapaSana AP-01"
    app_env: str = "development"
    tz_display: str = "America/Lima"
    frontend_url: str = "http://localhost:8080"
    cors_origins: str = "http://localhost:8080"

    database_url: str
    migration_database_url: str | None = None
    app_db_user: str = "papasana_app"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    refresh_cookie_name: str = "ps_refresh"
    refresh_cookie_path: str = "/api/v1"
    password_reset_minutes: int = 30

    redis_url: str = "redis://redis:6379/0"
    rate_limit_enabled: bool = True

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_secure: bool = False
    bucket_profiles: str = "perfiles"
    bucket_images: str = "imagenes"
    bucket_gradcam: str = "gradcam"
    bucket_reports: str = "reportes"

    ml_service_url: str = "http://ml-service:8001"
    ml_service_token: str = ""
    ml_timeout_seconds: float = 60.0
    max_image_bytes: int = 15 * 1024 * 1024

    # Fase 4: MLflow (tracking + Model Registry)
    mlflow_tracking_uri: str = ""
    mlflow_ui_url: str = "http://127.0.0.1:5000"
    mlflow_experiment: str = "papasana-ap01"
    mlflow_db_password: str = ""

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from: str = "no-responder@papasana.pe"

    demo_users_password: str | None = None
    max_photo_bytes: int = 2 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
