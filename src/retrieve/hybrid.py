from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from rank_bm25 import BM25Okapi

from src.retrieve.index import VectorIndex


def _tokenize(text: str) -> list[str]:
    # Include Latin letters with diacritics (PL) and Greek letters from abstracts.
    return re.findall(r"[a-z0-9α-ωà-öø-ÿąćęłńóśźż]+", text.lower(), flags=re.IGNORECASE)


class HybridRetriever:
    """Dense (Chroma) + sparse (BM25) with Reciprocal Rank Fusion."""

    def __init__(self, vector_index: VectorIndex, corpus_chunks: list[dict]):
        self.vector_index = vector_index
        self.chunks = corpus_chunks
        self._id_to_chunk = {c["id"]: c for c in corpus_chunks}
        tokenized = [_tokenize(c["text"]) for c in corpus_chunks]
        self.bm25 = BM25Okapi(tokenized) if tokenized else None

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[dict] = None,
        dense_weight: float = 1.0,
    ) -> list[dict]:
        dense = self.vector_index.query(query, top_k=max(top_k * 2, top_k), where=where)
        sparse: list[dict] = []
        if self.bm25 is not None:
            scores = self.bm25.get_scores(_tokenize(query))
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[
                : max(top_k * 2, top_k)
            ]
            for idx, score in ranked:
                chunk = self.chunks[idx]
                meta = chunk["metadata"]
                if where:
                    # Simple equality filters used by agent (year / topic_id).
                    ok = True
                    for key, expected in where.items():
                        if isinstance(expected, dict) and "$eq" in expected:
                            expected = expected["$eq"]
                        if meta.get(key) != expected:
                            ok = False
                            break
                    if not ok:
                        continue
                sparse.append(
                    {
                        "id": chunk["id"],
                        "text": chunk["text"],
                        "metadata": meta,
                        "score": float(score),
                        "distance": None,
                    }
                )

        fused = _rrf([dense, sparse], k=60)
        return fused[:top_k]


def _rrf(rankings: list[list[dict]], k: int = 60) -> list[dict]:
    scores: dict[str, float] = defaultdict(float)
    payloads: dict[str, dict] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            doc_id = item["id"]
            scores[doc_id] += 1.0 / (k + rank + 1)
            payloads[doc_id] = item
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out: list[dict] = []
    for doc_id, score in ordered:
        item = dict(payloads[doc_id])
        item["rrf_score"] = score
        out.append(item)
    return out
