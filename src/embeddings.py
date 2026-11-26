from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import get_settings


@lru_cache
def get_embedder(model_name: Optional[str] = None) -> SentenceTransformer:
    settings = get_settings()
    name = model_name or settings.embedding_model
    model = SentenceTransformer(name)
    if "bge-m3" in name:
        model.max_seq_length = 8192
    return model


def embed_texts(texts: list[str], model_name: Optional[str] = None) -> np.ndarray:
    model = get_embedder(model_name)
    vectors = model.encode(texts, show_progress_bar=len(texts) > 32, normalize_embeddings=True)
    return np.asarray(vectors, dtype=np.float32)


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
