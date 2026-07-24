from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://support:support@db:5432/support_triage"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    execution_mode: Literal["deterministic", "ai"] = "deterministic"
    zendesk_subdomain: str | None = None
    zendesk_email: str | None = None
    zendesk_api_token: str | None = None
    zendesk_webhook_signing_secret: str | None = None
    zendesk_note_sync_enabled: bool = False
    webhook_max_age_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
