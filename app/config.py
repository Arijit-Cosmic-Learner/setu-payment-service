"""
config.py
---------
Reads environment variables from .env file using Pydantic Settings.
All configuration for the app lives here in one place.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./setu_payments.db"

    # App
    APP_NAME: str = "Setu Payment Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


# Single instance used across the entire app
settings = Settings()

