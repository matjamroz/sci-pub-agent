from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from src.schemas import Abstract, Author, KeywordSet, Publication


_WS_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def _split_keyword_blob(raw: str | list[str]) -> list[str]:
    if isinstance(raw, list):
        tokens: list[str] = []
        for item in raw:
            tokens.extend(_split_keyword_blob(item))
        return tokens
    text = clean_text(str(raw))
    if not text:
        return []
    # Sample data often stores space-separated phrases in one string.
    parts = re.split(r"[;|/]+", text)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Keep PAC codes / multi-word phrases as-is when short; else split on
        # capitalized word boundaries loosely by keeping the blob tokens.
        if len(part.split()) <= 12:
            out.append(part)
        else:
            out.extend(t for t in part.split() if t)
    return out


def parse_raw_record(raw: dict) -> Publication:
    abstracts = [
        Abstract(
            language_code=a.get("languageCode") or "eng",
            content=clean_text(a.get("content") or ""),
        )
        for a in (raw.get("abstracts") or [])
    ]
    keyword_sets: list[KeywordSet] = []
    for ks in raw.get("keywords") or []:
        flattened: list[str] = []
        for blob in ks.get("keywords") or []:
            flattened.extend(_split_keyword_blob(blob))
        keyword_sets.append(
            KeywordSet(
                language_code=ks.get("languageCode") or "eng",
                keywords=flattened,
            )
        )
    authors = [
        Author(
            object_id=a.get("objectId"),
            name=clean_text(a.get("name") or ""),
            last_name=clean_text(a.get("lastName") or ""),
            uuid=a.get("uuid"),
            orcid_id=a.get("orcidId"),
            document_hash=a.get("documentHash"),
        )
        for a in (raw.get("authors") or [])
    ]
    return Publication(
        object_id=str(raw["objectId"]),
        title=clean_text(raw.get("title") or ""),
        year=raw.get("year"),
        doi=raw.get("doi"),
        abstracts=abstracts,
        keywords=keyword_sets,
        authors=authors,
    )


def load_jsonl(path: Path | str) -> list[Publication]:
    """Load publications from NDJSON or concatenated pretty-printed JSON objects."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    pubs: list[Publication] = []
    decoder = json.JSONDecoder()
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        try:
            raw, offset = decoder.raw_decode(text, idx)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON near offset {idx} in {path}") from exc
        pubs.append(parse_raw_record(raw))
        idx = offset
    return pubs


def iter_jsonl(path: Path | str) -> Iterable[Publication]:
    yield from load_jsonl(path)
