"""Ranking metrics from the evaluation plan: Recall@k and nDCG@k."""
from __future__ import annotations

import math


def recall_at_k(retrieved_ids: list[str], relevant: list[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(retrieved_ids[:k])
    return len(top & set(relevant)) / len(relevant)


def mrr(retrieved_ids: list[str], relevant: list[str]) -> float:
    rel = set(relevant)
    for i, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant: list[str], k: int) -> float:
    """Binary nDCG. A relevant publication scores more when it ranks higher."""
    if k <= 0 or not relevant:
        return 0.0
    rel = set(relevant)
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k], start=1):
        if doc_id in rel:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(rel), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg
