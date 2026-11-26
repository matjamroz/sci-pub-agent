#!/usr/bin/env python
"""Measure topic-cluster quality on a sample of the stored vectors."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.classify.evaluate import write_topic_evaluation
from src.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate topic clustering on a vector sample")
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=Path.home() / "Downloads" / "results (1)" / "embeddings_bge_m3",
    )
    parser.add_argument("--per-shard", type=int, default=80)
    parser.add_argument("--clusters", type=int, nargs="+", default=[4, 6, 8, 12])
    args = parser.parse_args()
    settings = get_settings()
    payload = write_topic_evaluation(
        args.embeddings,
        settings.models_dir,
        settings.sqlite_path,
        per_shard=args.per_shard,
        cluster_counts=tuple(args.clusters),
    )
    assigned = payload["assigned"]
    print(f"sample {payload['sample_size']}")
    print(f"silhouette_cosine {assigned.get('silhouette_cosine')}")
    print(f"davies_bouldin {assigned.get('davies_bouldin')}")
    print(f"calinski_harabasz {assigned.get('calinski_harabasz')}")
    print(f"mean_cosine_to_centroid {assigned.get('mean_cosine_to_centroid')}")
    print(f"keyword_hit_rate {assigned.get('keyword_hit_rate')}")
    for row in payload["k_comparison_on_sample"]:
        print(
            f"k={row['k']} silhouette={row['silhouette_cosine']} "
            f"davies_bouldin={row['davies_bouldin']} cosinus={row['mean_cosine_to_centroid']}"
        )
    print(f"wrote {settings.models_dir / 'clustering_metrics.json'}")


if __name__ == "__main__":
    main()
