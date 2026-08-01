"""Centralized application configuration.

All environment-dependent values are declared here and nowhere else,
so the rest of the codebase never calls os.getenv() directly.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App metadata ---
    app_name: str = Field(default="Personal Task Agent")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)

    # --- Server ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # --- Database ---
    database_path: str = Field(default="./personal_task_agent.db")

    # --- LLM (Groq) ---
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # --- Email (SMTP) ---
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_app_password: str = Field(default="")

    # --- Agent guardrails ---
    max_agent_steps: int = Field(default=8)

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_file_path: str = Field(default="./logs/app.log")

    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy connection URL for SQLite."""
        return f"sqlite:///{self.database_path}"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
