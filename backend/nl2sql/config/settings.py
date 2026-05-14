"""
config/settings.py
──────────────────
Central settings loaded from environment / .env file.
All other modules import from here — never read os.getenv directly.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "Customer Support NL2SQL"
    app_env: str = "development"
    app_secret_key: str = "change-me"
    debug: bool = True

    # ── Internal Postgres ────────────────────────────────────────────────────
    internal_db_host: str = "localhost"
    internal_db_port: int = 5432
    internal_db_name: str = "cs_nl2sql"
    internal_db_user: str = "postgres"
    internal_db_password: str = "postgres"

    @property
    def internal_db_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.internal_db_user}:{self.internal_db_password}"
            f"@{self.internal_db_host}:{self.internal_db_port}/{self.internal_db_name}"
        )

    @property
    def async_internal_db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.internal_db_user}:{self.internal_db_password}"
            f"@{self.internal_db_host}:{self.internal_db_port}/{self.internal_db_name}"
        )

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # ── NL2SQL Tuning ────────────────────────────────────────────────────────
    vector_similarity_threshold: float = 0.92
    max_sql_retries: int = 3
    max_rows_returned: int = 100

    # ── Sync ─────────────────────────────────────────────────────────────────
    sync_cron_interval_minutes: int = 30
    sync_batch_size: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()
