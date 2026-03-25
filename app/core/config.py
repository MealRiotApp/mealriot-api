from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str
    database_url: str
    openai_api_key: str
    admin_email: str
    frontend_url: str = "http://localhost:5173"
    internal_secret: str = "dev-internal-secret"
    dev_mode: bool = False
    smtp_host: str | None = None
    smtp_user: str | None = None
    smtp_pass: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        """Split comma-separated FRONTEND_URL into a list of origins."""
        return [u.strip() for u in self.frontend_url.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Convenience alias so existing imports don't break yet
settings = get_settings()
