# Architektura systemu

## Cel

Prototyp agenta konwersacyjnego typu RAG do pytań o trendy tematyczne oraz zależności współautorstwa w bazie publikacji naukowych.

## Komponenty

| Warstwa | Technologia | Rola |
|---------|-------------|------|
| Ingest | JSONL → Pydantic → SQLite | Normalizacja metadanych i grafu autorów |
| Klasyfikacja | sentence-transformers + KMeans (+ TF-IDF/LogReg) | Tematy publikacji |
| Indeks wektorowy | ChromaDB | Semantyczny retrieval |
| Hybrid search | BM25 + dense + RRF | Lepsze trafienia po słowach kluczowych |
| Analityka | SQL tools | Trendy, top tematy, profil autora, graf współautorów |
| LLM | Ollama / OpenAI-compatible | Synteza odpowiedzi grounded w tools + źródłach |
| API | FastAPI | `/health`, `/ask`, `/ingest` |
| UI | Streamlit + Plotly | Chat, źródła, wykresy |

## Przepływ zapytania

1. Użytkownik zadaje pytanie (UI lub API).
2. Router (`classify_intent`) wybiera ścieżkę: `semantic` | `trend` | `author` | `coauthor`.
3. Agent wywołuje narzędzia analityczne i/lub hybrid retrieval.
4. LLM (lub fallback deterministyczny) buduje odpowiedź wyłącznie na podstawie wyników.

## Ograniczenia danych próbnych

- Sample (~13 rekordów) ma wyłącznie rok `2000` → trendy czasowe są raportowane z ostrzeżeniem.
- Brak pól afiliacji/instytucji → MVP obejmuje relacje **autor ↔ temat ↔ współautorstwo**.
- Relacje instytucjonalne można dodać później (ORCID / OpenAlex) bez zmiany warstwy RAG.
