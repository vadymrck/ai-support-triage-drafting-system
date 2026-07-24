from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://support:support@db:5432/support_triage"
    openai_api_key: str | None = None
    # Environment variables are the runtime source of truth. These values make a
    # fresh local setup usable before an explicit override is supplied.
    openai_model: str = "gpt-5-mini"
    openai_judge_model: str = "gpt-5.6-terra"
    openai_embedding_model: str = "text-embedding-3-small"
    execution_mode: Literal["deterministic", "ai"] = "deterministic"
    hubspot_private_app_access_token: str | None = None
    hubspot_private_app_client_secret: str | None = None
    hubspot_webhook_base_url: str | None = None
    hubspot_note_sync_enabled: bool = False
    webhook_max_age_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
