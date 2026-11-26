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
    embedding_model: str = "BAAI/bge-m3"

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.2:3b"
    llm_temperature: float = 0.2
    llm_num_ctx: int = 2048
    llm_keep_alive: str = "30m"

    retrieval_top_k: int = 10
    chunk_max_chars: int = 3200
    chunk_overlap_chars: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
