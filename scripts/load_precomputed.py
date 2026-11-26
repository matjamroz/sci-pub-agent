#!/usr/bin/env python
"""Load Kaggle bge-m3 vectors into SQLite and Chroma without recomputing them."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.cluster import MiniBatchKMeans

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.classify.topics import save_topic_artifacts
from src.config import get_settings
from src.ingest.load_jsonl import parse_raw_record
from src.ingest.store import MetadataStore
from src.retrieve.index import VectorIndex


def iter_shards(folder: Path):
    vector_paths = sorted(folder.glob("vectors_*.npy"))
    if not vector_paths:
        raise FileNotFoundError(f"No vectors_*.npy in {folder}")
    for path in vector_paths:
        suffix = path.name[len("vectors_") : -len(".npy")]
        ids_path = folder / f"ids_{suffix}.txt"
        if not ids_path.exists():
            raise FileNotFoundError(ids_path)
        ids = [line.strip() for line in ids_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        vectors = np.load(path)
        if len(ids) != len(vectors):
            raise ValueError(f"{path.name} has {len(vectors)} rows but {ids_path.name} has {len(ids)} ids")
        yield suffix, ids, vectors


def iter_publications(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} of {path}") from exc
            yield parse_raw_record(raw)


def _rows_by_id(store: MetadataStore, object_ids: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    conn = store.connection()
    step = 500
    for start in range(0, len(object_ids), step):
        batch = object_ids[start : start + step]
        marks = ",".join("?" for _ in batch)
        pub_rows = conn.execute(
            f"""
            SELECT object_id, title, year, doi, search_text, keywords
            FROM publications
            WHERE object_id IN ({marks})
            """,
            batch,
        ).fetchall()
        for row in pub_rows:
            found[row["object_id"]] = {
                "title": row["title"] or "",
                "year": row["year"] if row["year"] is not None else -1,
                "doi": row["doi"] or "",
                "text": row["search_text"] or row["title"] or row["object_id"],
                "keywords": row["keywords"] or "",
                "author_keys": [],
                "author_names": [],
            }
        author_rows = conn.execute(
            f"""
            SELECT s.object_id, s.position, a.author_key, a.name, a.last_name
            FROM authorships s
            JOIN authors a ON a.author_key = s.author_key
            WHERE s.object_id IN ({marks})
            ORDER BY s.object_id, s.position
            """,
            batch,
        ).fetchall()
        for row in author_rows:
            item = found.get(row["object_id"])
            if item is None:
                continue
            item["author_keys"].append(row["author_key"])
            item["author_names"].append(f"{row['name']} {row['last_name']}".strip())
    missing = [object_id for object_id in object_ids if object_id not in found]
    if missing:
        raise KeyError(f"{len(missing)} vector ids are not in SQLite, first: {missing[0]}")
    return found


def _topic_label(counter: Counter[str]) -> str:
    if not counter:
        return "unlabeled"
    ranked = sorted(counter.items(), key=lambda item: (-item[1], len(item[0])))
    return " / ".join(token for token, _ in ranked[:3])[:120]


def load_sqlite(store: MetadataStore, jsonl_path: Path, expected: int) -> None:
    if store.count_publications() == expected:
        print(f"sqlite already has {expected} publications", flush=True)
        return
    print("loading publications into sqlite", flush=True)
    store.reset()
    batch = []
    total = 0
    for pub in iter_publications(jsonl_path):
        batch.append(pub)
        if len(batch) >= 1000:
            total += store.upsert_publications(batch)
            batch.clear()
            if total % 20000 == 0:
                print(f"  sqlite {total}", flush=True)
    if batch:
        total += store.upsert_publications(batch)
    if total != expected:
        raise ValueError(f"JSONL has {total} records, vectors have {expected}")
    print(f"  sqlite {total}", flush=True)


def fit_topics(folder: Path, k: int) -> MiniBatchKMeans:
    model = MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=4096, n_init=3)
    print("fitting topics on stored vectors", flush=True)
    for suffix, _ids, vectors in iter_shards(folder):
        model.partial_fit(vectors)
        print(f"  fit shard {suffix}", flush=True)
    return model


def assign_topics(store: MetadataStore, folder: Path, model: MiniBatchKMeans) -> dict[str, tuple[int, str]]:
    counts: dict[int, Counter[str]] = defaultdict(Counter)
    assigned: dict[str, int] = {}
    print("assigning topics", flush=True)
    for suffix, ids, vectors in iter_shards(folder):
        labels = model.predict(vectors)
        rows = _rows_by_id(store, ids)
        for object_id, label in zip(ids, labels.tolist()):
            topic_id = int(label)
            assigned[object_id] = topic_id
            for token in rows[object_id]["keywords"].split(" | "):
                token = token.strip()
                if len(token) >= 3:
                    counts[topic_id][token] += 1
        print(f"  topics shard {suffix}", flush=True)
    topic_info = {
        topic_id: {"label": _topic_label(counter), "keywords": "", "size": 0}
        for topic_id, counter in sorted(counts.items())
    }
    for topic_id in assigned.values():
        topic_info.setdefault(topic_id, {"label": "unlabeled", "keywords": "", "size": 0})
        topic_info[topic_id]["size"] += 1
    store.upsert_topics(topic_info)
    conn = store.connection()
    updates = [
        (topic_id, topic_info[topic_id]["label"], object_id) for object_id, topic_id in assigned.items()
    ]
    for start in range(0, len(updates), 5000):
        conn.executemany(
            "UPDATE publications SET topic_id = ?, topic_label = ? WHERE object_id = ?",
            updates[start : start + 5000],
        )
    conn.commit()
    mapping = {object_id: topic_id for object_id, topic_id in assigned.items()}
    save_topic_artifacts(get_settings().models_dir, topic_info, mapping)
    labeled = {object_id: (topic_id, topic_info[topic_id]["label"]) for object_id, topic_id in assigned.items()}
    print(f"  topics {len(topic_info)}", flush=True)
    return labeled


def load_chroma(
    store: MetadataStore,
    index: VectorIndex,
    folder: Path,
    topics: dict[str, tuple[int, str]],
    chunks_path: Path,
) -> int:
    print("writing chroma and chunks", flush=True)
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with chunks_path.open("w", encoding="utf-8") as handle:
        for suffix, ids, vectors in iter_shards(folder):
            rows = _rows_by_id(store, ids)
            documents = []
            metadatas = []
            chunk_ids = []
            for object_id in ids:
                row = rows[object_id]
                topic_id, topic_label = topics.get(object_id, (-1, ""))
                chunk_id = f"{object_id}::0"
                metadata = {
                    "object_id": object_id,
                    "title": row["title"][:500],
                    "year": int(row["year"]),
                    "doi": row["doi"][:200],
                    "topic_id": int(topic_id),
                    "topic_label": topic_label[:200],
                    "author_keys": "|".join(row["author_keys"])[:2000],
                    "author_names": "|".join(row["author_names"])[:2000],
                    "chunk_index": 0,
                }
                documents.append(row["text"])
                metadatas.append(metadata)
                chunk_ids.append(chunk_id)
                handle.write(
                    json.dumps(
                        {"id": chunk_id, "text": row["text"], "metadata": metadata},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            total += index.upsert_prepared(chunk_ids, documents, metadatas, vectors)
            print(f"  chroma shard {suffix} total {total}", flush=True)
    return total


def _write_topic_metrics(embeddings: Path, settings) -> None:
    try:
        from src.classify.evaluate import write_topic_evaluation

        payload = write_topic_evaluation(embeddings, settings.models_dir, settings.sqlite_path)
        score = payload["assigned"].get("silhouette_cosine")
        print(f"topic metrics silhouette_cosine {score}", flush=True)
    except Exception as exc:
        print(f"topic metrics failed: {exc}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load precomputed bge-m3 vectors")
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=Path.home() / "Downloads" / "results (1)" / "embeddings_bge_m3",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=Path.home() / "Downloads" / "publications.jsonl",
    )
    parser.add_argument("--clusters", type=int, default=6)
    args = parser.parse_args()

    meta_path = args.embeddings / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    expected = int(meta["processed_records"])
    if meta.get("model") != "BAAI/bge-m3":
        raise ValueError(f"Expected BAAI/bge-m3, got {meta.get('model')}")
    if int(meta.get("dimensions", 0)) != 1024:
        raise ValueError(f"Expected 1024 dimensions, got {meta.get('dimensions')}")

    settings = get_settings()
    store = MetadataStore(settings.sqlite_path)
    store.connection().execute("PRAGMA journal_mode = WAL")
    store.connection().execute("PRAGMA synchronous = NORMAL")
    load_sqlite(store, args.jsonl, expected)

    index = VectorIndex(settings.chroma_path)
    already = index.collection.count()
    if already == expected:
        print(f"chroma already has {expected} vectors", flush=True)
        store.close()
        _write_topic_metrics(args.embeddings, settings)
        return

    model = fit_topics(args.embeddings, args.clusters)
    topics = assign_topics(store, args.embeddings, model)
    index.reset()
    chunks_path = settings.data_dir / "processed" / "chunks.jsonl"
    written = load_chroma(store, index, args.embeddings, topics, chunks_path)
    summary = {
        "publications": store.count_publications(),
        "chunks": written,
        "year_span": store.year_span(),
        "sqlite": str(settings.sqlite_path),
        "chroma": str(settings.chroma_path),
        "embeddings": str(args.embeddings),
        "model": "BAAI/bge-m3",
    }
    processed = settings.data_dir / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    store.close()
    print("done", summary["publications"], "vectors", flush=True)
    _write_topic_metrics(args.embeddings, settings)


if __name__ == "__main__":
    main()
