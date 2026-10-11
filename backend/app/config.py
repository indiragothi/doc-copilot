from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Single source of truth for backend environment. Missing required vars fail at import."""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Direct/session connection (not the transaction pooler) — Alembic needs it.
    database_url: str

    openai_api_key: str
    openai_embedding_model: str
    openai_embedding_dimensions: int

    # PORT is the name Railway injects.
    host: str = "127.0.0.1"
    port: int = 8000

    # NoDecode: accept a plain comma-separated string instead of JSON.
    allowed_origins: Annotated[list[str], NoDecode]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
