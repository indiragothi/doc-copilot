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

    # Chat goes to Gemini, embeddings to NVIDIA's OpenAI-compatible API.
    gemini_api_key: str
    llm_model: str
    # Checks the answer's claims against its citations. A different model than the chat one,
    # because free-tier quota is counted per model and the judge must not eat the chat's.
    judge_model: str
    nvidia_api_key: str
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    embedding_model: str
    embedding_dimensions: int

    # Retrieval tuning; override with an env var of the same name (e.g. RETRIEVAL_TOP_K=10).
    retrieval_top_k: int = 8
    # Hits taken from each of the two searches before they are fused.
    retrieval_candidate_k: int = 50
    retrieval_rrf_k: int = 60
    # Chunks added on each side of a returned passage as context.
    retrieval_neighbor_radius: int = 1

    # Only used by `python -m app.main`; the Docker image passes host and port to uvicorn itself.
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
