import logging
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("dyscover.config")

# Used only when APP_ENV is development/test and no SECRET_KEY is supplied, so local
# sessions survive reloads. Production refuses to start with this (or any weak) key.
DEVELOPMENT_SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"
_KNOWN_PLACEHOLDERS = {
    "",
    "changeme",
    "changeme-in-production",
    "secret",
    "dev",
    DEVELOPMENT_SECRET_KEY,
}
MIN_SECRET_KEY_LENGTH = 32


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or unsafe."""


class Settings(BaseSettings):
    app_name: str = "Dyscover API"
    app_version: str = "0.2.0"
    app_env: str = "development"  # development | test | production
    secret_key: str = ""
    database_url: str = "sqlite:///./dyscover.db"
    cors_origins: str = "http://localhost:5173"
    api_version: str = "v1"
    api_version_prefix: str = "/api/v1"
    api_supported_versions: str = "v1"

    # Run ``alembic upgrade head`` at startup. Defaults to on outside production;
    # production deployments run migrations as an explicit release step.
    auto_migrate: bool | None = None

    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # Cookie flags for the refresh-token cookie. ``secure`` defaults to True in production.
    refresh_cookie_secure: bool | None = None
    refresh_cookie_samesite: str = "lax"

    # Rate limiting (slowapi syntax). Set RATE_LIMIT_ENABLED=false only in tests.
    rate_limit_enabled: bool = True
    rate_limit_default: str = "300/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_chat: str = "20/minute"

    # Lexi (Groq). Missing key => chat endpoints report "not configured" honestly.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: float = 30.0
    groq_max_history_messages: int = 20
    groq_max_output_tokens: int = 600

    # Uploaded audio limits for the speech demo endpoints.
    speech_upload_max_bytes: int = 10 * 1024 * 1024
    speech_transcription_timeout_seconds: float = 120.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        env = self.app_env.strip().lower()
        if env not in {"development", "test", "production"}:
            raise ConfigurationError(f"APP_ENV must be development, test or production (got {self.app_env!r})")
        self.app_env = env
        if self.is_production:
            if self.secret_key.strip().lower() in _KNOWN_PLACEHOLDERS or len(self.secret_key) < MIN_SECRET_KEY_LENGTH:
                raise ConfigurationError(
                    "SECRET_KEY must be set to a random value of at least "
                    f"{MIN_SECRET_KEY_LENGTH} characters in production "
                    "(e.g. python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
                )
            if "*" in self.cors_origin_list:
                raise ConfigurationError("CORS_ORIGINS may not contain '*' in production.")
            if self.refresh_cookie_samesite.lower() == "none" and self.refresh_cookie_secure is False:
                raise ConfigurationError("SameSite=None refresh cookies require REFRESH_COOKIE_SECURE=true.")
        elif not self.secret_key:
            self.secret_key = DEVELOPMENT_SECRET_KEY
        if self.refresh_cookie_samesite.lower() not in {"lax", "strict", "none"}:
            raise ConfigurationError("REFRESH_COOKIE_SAMESITE must be lax, strict or none.")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def should_auto_migrate(self) -> bool:
        return (not self.is_production) if self.auto_migrate is None else self.auto_migrate

    @property
    def cookie_secure(self) -> bool:
        return self.is_production if self.refresh_cookie_secure is None else self.refresh_cookie_secure

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def api_supported_versions_list(self) -> list[str]:
        return [v.strip() for v in self.api_supported_versions.split(",") if v.strip()]

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key.strip()) and bool(self.groq_model.strip())


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.secret_key == DEVELOPMENT_SECRET_KEY:
        logger.warning("SECRET_KEY not set; using the development-only signing key (APP_ENV=%s).", settings.app_env)
    return settings
