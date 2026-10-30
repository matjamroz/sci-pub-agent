from __future__ import annotations

from src.schemas import Publication


def chunk_publication(
    pub: Publication,
    max_chars: int = 3200,
    overlap: int = 200,
) -> list[dict]:
    """Build text chunks for embedding. Short records → single chunk."""
    base = pub.searchable_text()
    if not base:
        base = pub.title or pub.object_id

    meta = {
        "object_id": pub.object_id,
        "title": pub.title,
        "year": pub.year if pub.year is not None else -1,
        "doi": pub.doi or "",
        "topic_id": pub.topic_id if pub.topic_id is not None else -1,
        "topic_label": pub.topic_label or "",
        "author_keys": "|".join(a.author_key for a in pub.authors),
        "author_names": "|".join(a.full_name for a in pub.authors),
    }

    if len(base) <= max_chars:
        return [{"id": f"{pub.object_id}::0", "text": base, "metadata": {**meta, "chunk_index": 0}}]

    chunks: list[dict] = []
    start = 0
    idx = 0
    while start < len(base):
        end = min(len(base), start + max_chars)
        piece = base[start:end].strip()
        if piece:
            chunks.append(
                {
                    "id": f"{pub.object_id}::{idx}",
                    "text": piece,
                    "metadata": {**meta, "chunk_index": idx},
                }
            )
            idx += 1
        if end >= len(base):
            break
        start = max(0, end - overlap)
    return chunks
