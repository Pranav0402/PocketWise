from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PocketWise API"
    secret_key: str
    access_token_minutes: int = Field(default=60 * 24, ge=5, le=10080)
    database_url: str = "sqlite:///./pocketwise.db"
    cors_origins: str = "http://localhost:5173"
    app_environment: str = "development"
    auto_migrate: bool = True
    assistant_provider: str = "rules"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.app_environment.casefold() == "production":
            if len(self.secret_key) < 32 or self.secret_key.startswith("replace-with-"):
                raise ValueError("Production requires a randomly generated SECRET_KEY of at least 32 characters")
            origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
            if not origins or "*" in origins:
                raise ValueError("Production CORS_ORIGINS must list explicit trusted origins")
            if any(not origin.startswith("https://") for origin in origins):
                raise ValueError("Production CORS origins must use HTTPS")
            if self.auto_migrate:
                raise ValueError("Production requires AUTO_MIGRATE=false; run database upgrades explicitly")
        return self


settings = Settings()
