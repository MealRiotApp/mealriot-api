from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_jwt_secret: str
    supabase_service_key: str
    database_url: str
    openai_api_key: str
    admin_email: str
    frontend_url: str = "http://localhost:5173"

settings = Settings()
