"""
Centralized configuration using Pydantic Settings.

Loads configuration from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/lycia"

    # Session
    session_secret: str = "dev-secret-change-in-production-min-32-chars!"
    session_max_age: int = 7 * 24 * 60 * 60  # 7 days in seconds

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Application
    app_title: str = "Legacy of Lycia API"
    debug: bool = False


# Global settings instance
settings = Settings()
