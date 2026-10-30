from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT: Path = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = ROOT / "data"
    sqlite_path: Path = ROOT / "data" / "processed" / "publications.db"
    chroma_path: Path = ROOT / "data" / "processed" / "chroma"
    models_dir: Path = ROOT / "models" / "topic_model"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.1"
    llm_temperature: float = 0.2

    retrieval_top_k: int = 5
    chunk_max_chars: int = 3200
    chunk_overlap_chars: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
