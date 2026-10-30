from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from src.embeddings import embed_texts, save_json
from src.schemas import Publication


def _choose_k(n: int) -> int:
    if n < 3:
        return 1
    if n < 8:
        return 2
    return min(6, max(2, int(np.sqrt(n))))


def _label_from_keywords(pubs: list[Publication], indices: list[int]) -> str:
    counter: Counter[str] = Counter()
    for i in indices:
        for kw in pubs[i].keyword_list():
            token = kw.strip()
            if len(token) < 3:
                continue
            lower = token.lower()
            if "classification scheme" in lower or lower.startswith("["):
                continue
            # Prefer multi-word scientific phrases under ~8 tokens.
            if len(token.split()) > 10:
                for part in token.split():
                    if len(part) > 3 and part.lower() not in {
                        "with",
                        "from",
                        "that",
                        "this",
                        "and",
                        "the",
                    }:
                        counter[part] += 1
                continue
            counter[token] += 2
    if not counter:
        # Fallback: first meaningful title words
        titles = [pubs[i].title for i in indices if pubs[i].title]
        if titles:
            return titles[0][:80]
        return "unlabeled"
    ranked = sorted(counter.items(), key=lambda x: (-x[1], len(x[0])))
    top = [t for t, _ in ranked[:3]]
    return " / ".join(top)[:120]


def cluster_topics(
    pubs: list[Publication],
    n_clusters: Optional[int] = None,
    embedding_model: Optional[str] = None,
) -> tuple[list[Publication], dict[int, dict]]:
    texts = [p.searchable_text() or p.title for p in pubs]
    vectors = embed_texts(texts, model_name=embedding_model)
    k = n_clusters or _choose_k(len(pubs))
    if k == 1:
        labels = np.zeros(len(pubs), dtype=int)
    else:
        model = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = model.fit_predict(vectors)

    groups: dict[int, list[int]] = defaultdict(list)
    for idx, lab in enumerate(labels.tolist()):
        groups[int(lab)].append(idx)

    topic_info: dict[int, dict] = {}
    for topic_id, idxs in sorted(groups.items()):
        label = _label_from_keywords(pubs, idxs)
        topic_info[topic_id] = {
            "label": label,
            "keywords": " | ".join(
                " ".join(pubs[i].keyword_list()[:3]) for i in idxs[:5]
            ),
            "size": len(idxs),
        }

    out: list[Publication] = []
    for pub, lab in zip(pubs, labels.tolist()):
        tid = int(lab)
        out.append(
            pub.model_copy(update={"topic_id": tid, "topic_label": topic_info[tid]["label"]})
        )
    return out, topic_info


def save_topic_artifacts(
    models_dir: Path,
    topic_info: dict[int, dict],
    object_id_to_topic: dict[str, int],
) -> None:
    models_dir.mkdir(parents=True, exist_ok=True)
    save_json(models_dir / "topic_labels.json", {str(k): v for k, v in topic_info.items()})
    save_json(models_dir / "publication_topics.json", object_id_to_topic)


def weak_label_from_keywords(pub: Publication) -> str:
    kws = pub.keyword_list()
    if not kws:
        return "unknown"
    raw = re.sub(r"\[.*?\]", "", kws[0]).strip()
    tokens = raw.split()
    return " ".join(tokens[:4]).strip().lower() or "unknown"


def train_supervised_classifier(
    pubs: list[Publication],
    models_dir: Path,
    test_size: float = 0.3,
) -> dict:
    texts = [p.searchable_text() or p.title for p in pubs]
    y_raw = [weak_label_from_keywords(p) for p in pubs]
    encoder = LabelEncoder()
    y = encoder.fit_transform(y_raw)

    unique = len(set(y_raw))
    report: dict = {"n": len(pubs), "n_labels": unique, "labels": encoder.classes_.tolist()}

    pipe = Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )

    if len(pubs) >= 8 and unique >= 2 and test_size > 0:
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                texts, y, test_size=test_size, random_state=42, stratify=y
            )
        except ValueError:
            X_train, X_test, y_train, y_test = train_test_split(
                texts, y, test_size=test_size, random_state=42
            )
        pipe.fit(X_train, y_train)
        pred = pipe.predict(X_test)
        report["f1_macro"] = float(f1_score(y_test, pred, average="macro", zero_division=0))
        present = sorted(set(y_test.tolist()) | set(pred.tolist()))
        names = [str(encoder.classes_[i]) for i in present]
        report["classification_report"] = classification_report(
            y_test,
            pred,
            labels=present,
            target_names=names,
            zero_division=0,
        )
    else:
        pipe.fit(texts, y)
        pred = pipe.predict(texts)
        report["f1_macro"] = float(f1_score(y, pred, average="macro", zero_division=0))
        report["note"] = "Trained/evaluated on full tiny sample (no hold-out)."
        present = sorted(set(y.tolist()) | set(pred.tolist()))
        names = [str(encoder.classes_[i]) for i in present]
        report["classification_report"] = classification_report(
            y,
            pred,
            labels=present,
            target_names=names,
            zero_division=0,
        )

    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipe, "encoder": encoder}, models_dir / "supervised_clf.joblib")
    save_json(
        models_dir / "supervised_metrics.json",
        {k: v for k, v in report.items() if k != "classification_report"},
    )
    (models_dir / "supervised_report.txt").write_text(
        report.get("classification_report", json.dumps(report, indent=2)),
        encoding="utf-8",
    )
    return report
