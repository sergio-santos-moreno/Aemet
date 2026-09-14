"""
Centralised application configuration.

Everything that can change between environments (API keys, DB location,
log level...) is read from environment variables / a local .env file and
never hardcoded, following 12-factor-app practice. This also means the
AEMET_API_KEY requested in the challenge statement never touches source
control: only `.env.example` (with a placeholder) is committed.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aemet_api_key: str
    aemet_base_url: str = "https://opendata.aemet.es/opendata"

    database_url: str = "sqlite:///./aemet_cache.db"
    cache_ttl_minutes: int = 30

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings singleton.

    Using lru_cache (instead of a plain module-level instance) makes it
    trivial to override settings in tests via `get_settings.cache_clear()`
    plus monkeypatched env vars, and plays nicely with FastAPI's
    dependency-override mechanism if we ever need it.
    """
    return Settings()
