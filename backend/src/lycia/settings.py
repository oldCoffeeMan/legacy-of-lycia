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

    # Tick System
    tick_interval_seconds: float = 2.0  # Dev: 1-2s, Prod: 5-15s
    tick_enabled: bool = True  # Allow disabling tick loop for testing

    # Event Sourcing & Snapshots (S2-04)
    snapshot_frequency: int = 60  # Create snapshot every N ticks
    enable_event_sourcing: bool = True  # Enable event logging
    event_batch_size: int = 1000  # Max events to process in single replay batch


# Global settings instance
settings = Settings()
