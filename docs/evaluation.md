# Ewaluacja

## Zestaw testowy

Plik [`eval/questions.jsonl`](../eval/questions.jsonl) zawiera pytania w kategoriach:

- `retrieval` — czy właściwa publikacja jest w top-k
- `analytics` — poprawny intent i wywołanie toola
- `factual` — groundedness (obecność kluczowych faktów w odpowiedzi / źródłach)
- `classification` — pytania o tematy / klastry

## Metryki

- **Recall@k**, **MRR** (retrieval)
- **intent accuracy**, **tool accuracy**
- **factual hit rate**
- średnie **latency**

## Uruchomienie

Najpierw zbuduj indeks, potem:

```bash
python scripts/run_eval.py
```

Wyniki: `eval/results.json`.

## Wyniki (sample, run lokalny)

| Metryka | Wartość |
|---------|---------|
| Recall@5 | 1.0 |
| MRR | 1.0 |
| Intent accuracy | 1.0 |
| Tool accuracy | 1.0 |
| Factual hit rate | 1.0 |
| Latency mean (s) | 1.091 |

## Uwagi

Na sample z jednym rokiem pytania trendowe weryfikują przede wszystkim routing i poprawność agregacji SQL, nie sensowność trendu czasowego.
