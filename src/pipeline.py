from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.analytics.tools import AnalyticsTools
from src.agent.orchestrator import AgentOrchestrator
from src.classify.topics import (
    cluster_topics,
    save_topic_artifacts,
    train_supervised_classifier,
)
from src.config import ROOT, get_settings
from src.ingest.chunking import chunk_publication
from src.ingest.load_jsonl import load_jsonl
from src.ingest.store import MetadataStore
from src.llm.client import LLMClient
from src.retrieve.index import VectorIndex, VectorRetriever


@dataclass
class Runtime:
    store: MetadataStore
    vector_index: VectorIndex
    retriever: VectorRetriever
    analytics: AnalyticsTools
    agent: AgentOrchestrator
    chunks: list[dict]


def default_jsonl_path() -> Path:
    settings = get_settings()
    candidate = settings.data_dir / "raw" / "publications-sample.jsonl"
    if candidate.exists():
        return candidate
    downloads = Path.home() / "Downloads" / "publications-sample.jsonl"
    if downloads.exists():
        return downloads
    return candidate


def build_index(
    jsonl_path: Optional[Path] = None,
    reset: bool = True,
    n_clusters: Optional[int] = None,
    train_supervised: bool = True,
) -> dict:
    settings = get_settings()
    path = Path(jsonl_path) if jsonl_path else default_jsonl_path()
    if not path.exists():
        raise FileNotFoundError(f"JSONL not found: {path}")

    # Ensure raw copy under project data/
    raw_dir = settings.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target_raw = raw_dir / path.name
    if path.resolve() != target_raw.resolve():
        target_raw.write_bytes(path.read_bytes())

    pubs = load_jsonl(target_raw)
    pubs, topic_info = cluster_topics(pubs, n_clusters=n_clusters)
    mapping = {p.object_id: int(p.topic_id) for p in pubs if p.topic_id is not None}
    save_topic_artifacts(settings.models_dir, topic_info, mapping)

    store = MetadataStore(settings.sqlite_path)
    if reset:
        store.reset()
    store.upsert_publications(pubs)
    store.upsert_topics(topic_info)

    chunks: list[dict] = []
    for pub in pubs:
        chunks.extend(
            chunk_publication(
                pub,
                max_chars=settings.chunk_max_chars,
                overlap=settings.chunk_overlap_chars,
            )
        )

    # Persist chunk corpus for BM25 reload
    processed = settings.data_dir / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    chunks_path = processed / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as fh:
        for ch in chunks:
            fh.write(json.dumps(ch, ensure_ascii=False) + "\n")

    index = VectorIndex(settings.chroma_path)
    if reset:
        index.reset()
    n_upserted = index.upsert_chunks(chunks)

    supervised_report = None
    if train_supervised:
        try:
            supervised_report = train_supervised_classifier(pubs, settings.models_dir)
        except Exception as exc:  # keep core index even if weak-label train fails
            supervised_report = {"error": str(exc)}

    summary = {
        "jsonl": str(target_raw),
        "publications": len(pubs),
        "chunks": n_upserted,
        "topics": topic_info,
        "year_span": store.year_span(),
        "sqlite": str(settings.sqlite_path),
        "chroma": str(settings.chroma_path),
        "supervised": supervised_report,
    }
    (processed / "build_summary.json").write_text(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k != "supervised"
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    store.close()
    return summary


def chunks_from_database(store: MetadataStore) -> list[dict]:
    """Lexical corpus kept for HybridRetriever. The answer path does not load it."""
    conn = store.connection()
    rows = conn.execute(
        "SELECT object_id, title, year, doi, abstract, keywords, topic_id, topic_label FROM publications"
    ).fetchall()
    chunks: list[dict] = []
    for r in rows:
        text = "\n\n".join(
            p for p in [r["title"], r["abstract"] or "", r["keywords"] or ""] if p
        )
        chunks.append(
            {
                "id": f"{r['object_id']}::0",
                "text": text,
                "metadata": {
                    "object_id": r["object_id"],
                    "title": r["title"],
                    "year": r["year"] if r["year"] is not None else -1,
                    "doi": r["doi"] or "",
                    "topic_id": r["topic_id"] if r["topic_id"] is not None else -1,
                    "topic_label": r["topic_label"] or "",
                    "author_keys": "",
                    "author_names": "",
                    "chunk_index": 0,
                },
            }
        )
    return chunks


def load_chunks(path: Optional[Path] = None) -> list[dict]:
    settings = get_settings()
    chunks_path = path or (settings.data_dir / "processed" / "chunks.jsonl")
    if not chunks_path.exists():
        return []
    out = []
    with chunks_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def get_runtime() -> Runtime:
    settings = get_settings()
    if not settings.sqlite_path.exists():
        build_index()
    store = MetadataStore(settings.sqlite_path)
    index = VectorIndex(settings.chroma_path)
    retriever = VectorRetriever(index)
    analytics = AnalyticsTools(store)
    agent = AgentOrchestrator(retriever, analytics, LLMClient())
    return Runtime(
        store=store,
        vector_index=index,
        retriever=retriever,
        analytics=analytics,
        agent=agent,
        chunks=[],
    )
