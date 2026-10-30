#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.classify.topics import train_supervised_classifier
from src.ingest.load_jsonl import load_jsonl
from src.pipeline import default_jsonl_path
from src.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Train weak-label supervised classifier")
    parser.add_argument("--jsonl", type=Path, default=None)
    args = parser.parse_args()
    pubs = load_jsonl(args.jsonl or default_jsonl_path())
    report = train_supervised_classifier(pubs, get_settings().models_dir)
    print(report.get("classification_report") or report)


if __name__ == "__main__":
    main()
