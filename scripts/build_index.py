#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import build_index, default_jsonl_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SQLite + Chroma index")
    parser.add_argument("--jsonl", type=Path, default=None)
    parser.add_argument("--n-clusters", type=int, default=None)
    parser.add_argument("--no-supervised", action="store_true")
    args = parser.parse_args()
    path = args.jsonl or default_jsonl_path()
    summary = build_index(
        jsonl_path=path,
        reset=True,
        n_clusters=args.n_clusters,
        train_supervised=not args.no_supervised,
    )
    print("Build complete:")
    for key in ("jsonl", "publications", "chunks", "year_span", "sqlite", "chroma"):
        print(f"  {key}: {summary.get(key)}")
    print("  topics:")
    for tid, info in (summary.get("topics") or {}).items():
        print(f"    [{tid}] {info.get('label')} (n={info.get('size')})")
    if summary.get("supervised"):
        print(f"  supervised f1_macro: {summary['supervised'].get('f1_macro')}")


if __name__ == "__main__":
    main()
