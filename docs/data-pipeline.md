# Pipeline danych

## Wejście

Plik JSONL, rekord per linia. Pola używane:

- `objectId`, `title`, `year`, `doi`
- `abstracts[]` (`languageCode`, `content`) — preferowany `eng`
- `keywords[]` — frazy / kody klasyfikacyjne
- `authors[]` — `name`, `lastName`, `orcidId`, `uuid`, `objectId`

## Kroki

1. **Load & normalize** (`src/ingest/load_jsonl.py`)
2. **Topic clustering** (`src/classify/topics.py`) na embeddingach title+abstract
3. **Supervised weak-label baseline** (TF-IDF + LogisticRegression) → `models/topic_model/`
4. **SQLite upsert** publikacji, autorów, authorships, topics
5. **Chunking** (zwykle 1 chunk = title + abstract + keywords)
6. **Chroma upsert** z metadanymi (`object_id`, `year`, `topic_*`, autorzy)
7. Zapis `data/processed/chunks.jsonl` pod BM25

## Uruchomienie

```bash
python scripts/inspect_data.py
python scripts/build_index.py
```

Pełniejszy, wieloletni JSONL podawaj przez:

```bash
python scripts/build_index.py --jsonl path/do/duzy.jsonl
```

lub `POST /ingest` z `{"jsonl_path": "..."}`.
