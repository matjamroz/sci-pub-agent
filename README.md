# Sci-Pub Agent

Agent konwersacyjny (RAG) do pytań o trendy, tematy i zależności współautorstwa w publikacjach naukowych.

Temat dyplomu: *An Agent for Answering Questions on Trends and Dependencies in Scientific Publications*.

## Wymagania

- Python 3.11+
- (opcjonalnie) [Ollama](https://ollama.com) z modelem `llama3.2:3b` — bez LLM działa fallback deterministyczny

## Szybki start (Windows)

```powershell
cd C:\Users\matja\Projects\sci-pub-agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

# Dane próbne są w data/raw/ — zbuduj SQLite + Chroma + tematy:
python scripts/build_index.py

# API
uvicorn src.api.main:app --reload --port 8000

# UI (w drugim terminalu)
streamlit run ui/app.py
```

## Przykładowe pytania

- `What paper discusses neutrino mixing angles and fixed points?`
- `Jakie są najpopularniejsze tematy?`
- `Profil autora Paweł Kulesza`
- `Współautorzy dla Krzysztof Miecznikowski`

## Skrypty

| Skrypt | Opis |
|--------|------|
| `scripts/inspect_data.py` | Statystyki JSONL |
| `scripts/build_index.py` | ETL + klasyfikacja + indeks |
| `scripts/train_classifier.py` | Weak-label supervised baseline |
| `scripts/run_eval.py` | Recall@k / MRR / intent / tools |

## Dokumentacja

- [Architektura](docs/architecture.md)
- [Pipeline danych](docs/data-pipeline.md)
- [Ewaluacja](docs/evaluation.md)

## Ograniczenia sample

- 13 publikacji, wszystkie z roku 2000
- Brak afiliacji/instytucji w JSONL — MVP: autor ↔ temat ↔ współautorstwo
