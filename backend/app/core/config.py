from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Dyscover API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    database_url: str = "sqlite:///./dyscover.db"
    cors_origins: str = "http://localhost:5173"
    api_version: str = "v1"
    api_version_prefix: str = "/api/v1"
    api_supported_versions: str = "v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def api_supported_versions_list(self) -> list[str]:
        return [v.strip() for v in self.api_supported_versions.split(",") if v.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
