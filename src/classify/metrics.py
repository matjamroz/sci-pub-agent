"""Quality measures for topic clusters. There is no official discipline label."""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "from",
        "in",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "dla",
        "i",
        "na",
        "oraz",
        "w",
        "z",
    }
)


def normalize_rows(vectors: np.ndarray) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


def content_terms(label: str) -> list[str]:
    terms = []
    for part in label.split("/"):
        token = " ".join(part.strip().casefold().split())
        if len(token) < 3 or token in STOPWORDS:
            continue
        terms.append(token)
    return terms


def keyword_matches(keywords: Iterable[str], terms: Iterable[str]) -> bool:
    keys = [" ".join(item.strip().casefold().split()) for item in keywords if item and item.strip()]
    wanted = [term for term in terms if term]
    if not keys or not wanted:
        return False
    for term in wanted:
        for key in keys:
            if key == term or term in key:
                return True
    return False


def clustering_scores(vectors: np.ndarray, labels: np.ndarray) -> dict:
    """Scores on one sample. Higher silhouette, Calinski-Harabasz and cosine are tighter clusters."""
    matrix = normalize_rows(vectors)
    assigned = np.asarray(labels, dtype=int)
    if len(matrix) != len(assigned):
        raise ValueError("vectors and labels must have the same length")
    unique, counts = np.unique(assigned, return_counts=True)
    sizes = {int(label): int(count) for label, count in zip(unique, counts)}
    centroids = []
    order = [int(label) for label in unique]
    per_cluster: dict[int, dict] = {}
    own_parts = []
    for label in order:
        block = matrix[assigned == label]
        centroid = block.mean(axis=0)
        centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-12)
        centroids.append(centroid)
        sims = block @ centroid
        per_cluster[label] = {
            "sample_size": int(len(block)),
            "mean_cosine_to_centroid": float(sims.mean()),
        }
        own_parts.append(sims)
    own = np.concatenate(own_parts) if own_parts else np.array([], dtype=np.float64)
    margin = None
    if len(order) >= 2 and len(own):
        table = np.vstack(centroids)
        sims = matrix @ table.T
        index = {label: pos for pos, label in enumerate(order)}
        own_index = np.array([index[int(label)] for label in assigned])
        own_sim = sims[np.arange(len(assigned)), own_index]
        sims[np.arange(len(assigned)), own_index] = -np.inf
        margin = own_sim - sims.max(axis=1)
    usable = len(order) >= 2 and len(assigned) > len(order) and int(counts.min()) >= 2
    silhouette = float(silhouette_score(matrix, assigned, metric="cosine")) if usable else None
    davies = float(davies_bouldin_score(matrix, assigned)) if usable else None
    calinski = float(calinski_harabasz_score(matrix, assigned)) if usable else None
    return {
        "sample_size": int(len(assigned)),
        "n_clusters": int(len(order)),
        "sizes": sizes,
        "mean_cosine_to_centroid": float(own.mean()) if len(own) else None,
        "mean_margin_to_other_centroid": float(margin.mean()) if margin is not None else None,
        "silhouette_cosine": silhouette,
        "davies_bouldin": davies,
        "calinski_harabasz": calinski,
        "per_cluster": per_cluster,
    }


def compare_cluster_counts(
    vectors: np.ndarray,
    cluster_counts: Iterable[int],
    random_state: int = 42,
    n_init: int = 10,
) -> list[dict]:
    """Fit KMeans on this sample for several k. Does not change labels stored for the corpus."""
    matrix = normalize_rows(vectors)
    rows = []
    for k in cluster_counts:
        k = int(k)
        if k < 2 or k >= len(matrix):
            continue
        model = KMeans(n_clusters=k, random_state=random_state, n_init=n_init)
        labels = model.fit_predict(matrix)
        scores = clustering_scores(matrix, labels)
        rows.append(
            {
                "k": k,
                "inertia": float(model.inertia_),
                "silhouette_cosine": scores["silhouette_cosine"],
                "davies_bouldin": scores["davies_bouldin"],
                "calinski_harabasz": scores["calinski_harabasz"],
                "mean_cosine_to_centroid": scores["mean_cosine_to_centroid"],
                "mean_margin_to_other_centroid": scores["mean_margin_to_other_centroid"],
            }
        )
    return rows


def label_agreement(
    keyword_rows: list[list[str]],
    labels: np.ndarray,
    label_names: dict[int, str],
) -> dict:
    """Share of sampled papers whose keywords contain a content term from the cluster name."""
    assigned = np.asarray(labels, dtype=int)
    per_cluster: dict[int, dict] = {}
    hits = 0
    checked = 0
    without_keywords = 0
    for keywords, label in zip(keyword_rows, assigned.tolist()):
        label = int(label)
        bucket = per_cluster.setdefault(
            label,
            {"with_keywords": 0, "hits": 0, "terms": content_terms(label_names.get(label, ""))},
        )
        if not any(item.strip() for item in keywords):
            without_keywords += 1
            continue
        bucket["with_keywords"] += 1
        checked += 1
        if keyword_matches(keywords, bucket["terms"]):
            bucket["hits"] += 1
            hits += 1
    for bucket in per_cluster.values():
        total = bucket["with_keywords"]
        bucket["hit_rate"] = (bucket["hits"] / total) if total else None
    return {
        "hit_rate": (hits / checked) if checked else None,
        "papers_with_keywords": checked,
        "papers_without_keywords": without_keywords,
        "per_cluster": per_cluster,
    }
