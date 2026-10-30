#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingest.load_jsonl import load_jsonl
from src.pipeline import default_jsonl_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect publications JSONL")
    parser.add_argument("--jsonl", type=Path, default=None)
    args = parser.parse_args()
    path = args.jsonl or default_jsonl_path()
    pubs = load_jsonl(path)

    years = Counter(p.year for p in pubs if p.year is not None)
    missing_abs = sum(1 for p in pubs if not p.primary_abstract())
    lengths = [len(p.primary_abstract()) for p in pubs]
    n_authors = sum(len(p.authors) for p in pubs)

    report = {
        "path": str(path),
        "n_publications": len(pubs),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "years": dict(sorted(years.items())),
        "missing_abstracts": missing_abs,
        "abstract_len_avg": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "abstract_len_min": min(lengths) if lengths else 0,
        "abstract_len_max": max(lengths) if lengths else 0,
        "n_authorships": n_authors,
        "unique_author_keys": len({a.author_key for p in pubs for a in p.authors}),
        "with_doi": sum(1 for p in pubs if p.doi),
        "sample_titles": [p.title for p in pubs[:5]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
