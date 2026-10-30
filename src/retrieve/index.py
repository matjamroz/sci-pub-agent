from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import get_settings
from src.embeddings import embed_texts


class VectorIndex:
    def __init__(
        self,
        persist_path: Optional[Path] = None,
        collection_name: str = "publications",
    ):
        settings = get_settings()
        self.persist_path = Path(persist_path or settings.chroma_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self) -> None:
        name = self.collection.name
        self.client.delete_collection(name)
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(self, chunks: list[dict]) -> int:
        if not chunks:
            return 0
        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        embeddings = embed_texts(documents).tolist()
        # Chroma upsert in batches
        batch = 64
        for i in range(0, len(ids), batch):
            self.collection.upsert(
                ids=ids[i : i + batch],
                documents=documents[i : i + batch],
                metadatas=metadatas[i : i + batch],
                embeddings=embeddings[i : i + batch],
            )
        return len(ids)

    def query(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict]:
        emb = embed_texts([query]).tolist()
        kwargs: dict[str, Any] = {
            "query_embeddings": emb,
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        result = self.collection.query(**kwargs)
        hits: list[dict] = []
        if not result or not result.get("ids"):
            return hits
        for i, doc_id in enumerate(result["ids"][0]):
            meta = result["metadatas"][0][i] if result["metadatas"] else {}
            dist = result["distances"][0][i] if result["distances"] else None
            hits.append(
                {
                    "id": doc_id,
                    "text": result["documents"][0][i] if result["documents"] else "",
                    "metadata": meta,
                    "distance": dist,
                    "score": None if dist is None else 1.0 - float(dist),
                }
            )
        return hits
