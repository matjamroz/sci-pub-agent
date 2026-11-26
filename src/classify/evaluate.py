"""Sample stored bge-m3 vectors and write clustering quality files."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from src.classify.metrics import clustering_scores, compare_cluster_counts, label_agreement
from src.embeddings import save_json


def sample_shard_rows(folder: Path, per_shard: int, seed: int) -> tuple[list[str], np.ndarray]:
    rng = np.random.default_rng(seed)
    ids_out: list[str] = []
    blocks = []
    vector_paths = sorted(folder.glob("vectors_*.npy"))
    if not vector_paths:
        raise FileNotFoundError(f"No vectors_*.npy in {folder}")
    for path in vector_paths:
        suffix = path.name[len("vectors_") : -len(".npy")]
        ids_path = folder / f"ids_{suffix}.txt"
        ids = [line.strip() for line in ids_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        matrix = np.load(path, mmap_mode="r")
        if len(ids) != len(matrix):
            raise ValueError(f"{path.name} has {len(matrix)} rows but {ids_path.name} has {len(ids)} ids")
        take = min(per_shard, len(ids))
        chosen = np.sort(rng.choice(len(ids), size=take, replace=False))
        blocks.append(np.array(matrix[chosen], dtype=np.float32))
        ids_out.extend(ids[int(i)] for i in chosen)
        del matrix
    return ids_out, np.vstack(blocks)


def _read_sample_rows(sqlite_path: Path, object_ids: list[str]) -> dict[str, dict]:
    uri = sqlite_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=60)
    conn.row_factory = sqlite3.Row
    found: dict[str, dict] = {}
    try:
        for start in range(0, len(object_ids), 400):
            batch = object_ids[start : start + 400]
            marks = ",".join("?" for _ in batch)
            rows = conn.execute(
                f"""
                SELECT object_id, title, year, keywords
                FROM publications
                WHERE object_id IN ({marks})
                """,
                batch,
            ).fetchall()
            for row in rows:
                found[row["object_id"]] = {
                    "title": row["title"] or "",
                    "year": row["year"],
                    "keywords": [part.strip() for part in (row["keywords"] or "").split("|") if part.strip()],
                }
    finally:
        conn.close()
    return found


def _examples(rows: dict[str, dict], object_ids: list[str], labels: np.ndarray, limit: int) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for object_id, label in zip(object_ids, labels.tolist()):
        key = str(int(label))
        bucket = grouped.setdefault(key, [])
        if len(bucket) >= limit:
            continue
        meta = rows.get(object_id) or {}
        title = meta.get("title") or object_id
        bucket.append({"object_id": object_id, "year": meta.get("year"), "title": title[:180]})
    return grouped


def write_topic_evaluation(
    embeddings_dir: Path,
    models_dir: Path,
    sqlite_path: Path,
    per_shard: int = 80,
    cluster_counts: tuple[int, ...] = (4, 6, 8, 12),
    seed: int = 42,
    examples_per_cluster: int = 8,
) -> dict:
    mapping = json.loads((models_dir / "publication_topics.json").read_text(encoding="utf-8"))
    stored = json.loads((models_dir / "topic_labels.json").read_text(encoding="utf-8"))
    names = {int(key): str(info.get("label") or "") for key, info in stored.items()}
    full_sizes = {str(key): int(info.get("size") or 0) for key, info in stored.items()}

    object_ids, vectors = sample_shard_rows(embeddings_dir, per_shard, seed)
    known = [i for i, object_id in enumerate(object_ids) if object_id in mapping]
    labeled_ids = [object_ids[i] for i in known]
    labeled_vectors = vectors[known]
    labeled = np.array([int(mapping[object_id]) for object_id in labeled_ids], dtype=int)

    assigned = clustering_scores(labeled_vectors, labeled)
    for label, info in assigned["per_cluster"].items():
        info["label"] = names.get(int(label), "")
        info["full_size"] = full_sizes.get(str(label), 0)

    try:
        meta = _read_sample_rows(sqlite_path, labeled_ids)
    except sqlite3.Error as exc:
        meta = {}
        assigned["metadata_error"] = str(exc)
    keyword_rows = [meta.get(object_id, {}).get("keywords", []) for object_id in labeled_ids]
    agreement = label_agreement(keyword_rows, labeled, names)
    for label, info in agreement["per_cluster"].items():
        target = assigned["per_cluster"].setdefault(int(label), {})
        target["keyword_hit_rate"] = info["hit_rate"]
        target["keyword_terms"] = info["terms"]
    assigned["keyword_hit_rate"] = agreement["hit_rate"]
    assigned["papers_with_keywords"] = agreement["papers_with_keywords"]
    assigned["papers_without_keywords"] = agreement["papers_without_keywords"]
    assigned["examples"] = _examples(meta, labeled_ids, labeled, examples_per_cluster)

    comparison = compare_cluster_counts(labeled_vectors, cluster_counts, random_state=seed)
    payload = {
        "assigned_model": "MiniBatchKMeans",
        "assigned_k": int(assigned["n_clusters"]),
        "sample_per_shard": per_shard,
        "sample_seed": seed,
        "sample_size": int(assigned["sample_size"]),
        "skipped_without_label": int(len(object_ids) - len(labeled_ids)),
        "full_sizes": full_sizes,
        "assigned": assigned,
        "k_comparison_on_sample": comparison,
        "reading": {
            "silhouette_cosine": "od -1 do 1, wyższa wartość oznacza ciaśniejsze i lepiej rozdzielone grupy",
            "davies_bouldin": "niższa wartość oznacza lepszy rozdział grup",
            "calinski_harabasz": "wyższa wartość oznacza lepszy rozdział grup",
            "mean_cosine_to_centroid": "średnie podobieństwo pracy do środka własnej grupy",
            "mean_margin_to_other_centroid": "o ile praca jest bliżej własnego środka niż najbliższego obcego",
            "keyword_hit_rate": "udział prac, których słowo kluczowe pokrywa się z nazwą grupy",
            "k_comparison_on_sample": "KMeans dopasowany tylko do tej próbki; nie zmienia kierunków zapisanych w bazie",
        },
    }
    (models_dir / "clustering_report.txt").write_text(_report_text(payload), encoding="utf-8")
    save_json(models_dir / "clustering_metrics.json", _json_ready(payload))
    return payload


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _num(value) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _report_text(payload: dict) -> str:
    assigned = payload["assigned"]
    lines = [
        "Ocena grupowania kierunków",
        f"Model zapisany w bazie: {payload['assigned_model']}, k={payload['assigned_k']}",
        (
            f"Próbka: {payload['sample_size']} publikacji "
            f"({payload['sample_per_shard']} losowych wierszy z każdego pliku wektorów, ziarno {payload['sample_seed']})."
        ),
        f"Silhouette (cosine): {_num(assigned.get('silhouette_cosine'))}",
        f"Davies-Bouldin: {_num(assigned.get('davies_bouldin'))}",
        f"Calinski-Harabasz: {_num(assigned.get('calinski_harabasz'))}",
        f"Średni cosinus do środka grupy: {_num(assigned.get('mean_cosine_to_centroid'))}",
        f"Średni margines do obcej grupy: {_num(assigned.get('mean_margin_to_other_centroid'))}",
        f"Zgodność nazwy ze słowem kluczowym: {_num(assigned.get('keyword_hit_rate'))}",
        "",
        "Grupy:",
    ]
    for label, info in sorted(assigned.get("per_cluster", {}).items(), key=lambda item: int(item[0])):
        lines.append(
            f"  {label}. {info.get('label')} | w zbiorze {info.get('full_size')} | "
            f"w próbce {info.get('sample_size')} | cosinus {_num(info.get('mean_cosine_to_centroid'))} | "
            f"zgodność nazwy {_num(info.get('keyword_hit_rate'))}"
        )
    lines.append("")
    lines.append("Porównanie liczby grup na tej samej próbce:")
    for row in payload.get("k_comparison_on_sample") or []:
        lines.append(
            f"  k={row['k']} silhouette={_num(row['silhouette_cosine'])} "
            f"davies_bouldin={_num(row['davies_bouldin'])} calinski={_num(row['calinski_harabasz'])} "
            f"cosinus={_num(row['mean_cosine_to_centroid'])}"
        )
    lines.append("")
    lines.append("Przykładowe tytuły z próbki:")
    for label, items in sorted((assigned.get("examples") or {}).items(), key=lambda item: int(item[0])):
        name = assigned.get("per_cluster", {}).get(int(label), {}).get("label", "")
        lines.append(f"  [{label}] {name}")
        for item in items:
            year = item.get("year")
            lines.append(f"    {year}: {item.get('title')}")
    lines.append("")
    return "\n".join(lines)
