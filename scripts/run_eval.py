#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.orchestrator import classify_intent
from src.pipeline import get_runtime
from src.retrieve.ranking import mrr, ndcg_at_k, recall_at_k


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation suite")
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT / "eval" / "questions.jsonl",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results.json")
    args = parser.parse_args()

    rt = get_runtime()
    rows = []
    with args.questions.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    retrieval_scores = []
    recall10_scores = []
    ndcg10_scores = []
    mrr_scores = []
    intent_ok = 0
    intent_n = 0
    tool_ok = 0
    tool_n = 0
    factual_ok = 0
    factual_n = 0
    latencies = []
    details = []

    for row in rows:
        q = row["question"]
        t0 = time.perf_counter()
        result = rt.agent.ask(q, top_k=args.top_k)
        dt = time.perf_counter() - t0
        latencies.append(dt)

        retrieved_ids = []
        for s in result.sources:
            oid = (s.get("metadata") or {}).get("object_id")
            if oid and oid not in retrieved_ids:
                retrieved_ids.append(oid)

        item = {
            "id": row.get("id"),
            "category": row.get("category"),
            "question": q,
            "intent_pred": result.intent,
            "latency_s": round(dt, 3),
            "retrieved_ids": retrieved_ids,
        }

        if row.get("category") == "retrieval" and row.get("relevant_ids"):
            ids_at_10 = retrieved_ids
            if len(retrieved_ids) < 10:
                extra = rt.retriever.search(q, top_k=10)
                ids_at_10 = []
                for hit in extra:
                    oid = (hit.get("metadata") or {}).get("object_id")
                    if oid and oid not in ids_at_10:
                        ids_at_10.append(oid)
            r = recall_at_k(retrieved_ids, row["relevant_ids"], args.top_k)
            r10 = recall_at_k(ids_at_10, row["relevant_ids"], 10)
            n10 = ndcg_at_k(ids_at_10, row["relevant_ids"], 10)
            m = mrr(retrieved_ids, row["relevant_ids"])
            retrieval_scores.append(r)
            recall10_scores.append(r10)
            ndcg10_scores.append(n10)
            mrr_scores.append(m)
            item["recall_at_k"] = r
            item["recall_at_10"] = r10
            item["ndcg_at_10"] = n10
            item["mrr"] = m

        if row.get("expect_intent"):
            intent_n += 1
            ok = classify_intent(q) == row["expect_intent"] or result.intent == row["expect_intent"]
            intent_ok += int(ok)
            item["intent_ok"] = ok

        if row.get("expect_tool"):
            tool_n += 1
            ok = row["expect_tool"] in (result.tool_results or {})
            tool_ok += int(ok)
            item["tool_ok"] = ok

        if row.get("must_contain_any"):
            factual_n += 1
            ans = result.answer or ""
            blob = ans + "\n" + json.dumps(result.tool_results, ensure_ascii=False)
            for s in result.sources:
                meta = s.get("metadata") or {}
                blob += "\n" + (s.get("text") or "")
                blob += "\n" + str(meta.get("title") or "")
                blob += "\n" + str(meta.get("year") or "")
                blob += "\n" + str(meta.get("author_names") or "")
            ok = any(tok.lower() in blob.lower() for tok in row["must_contain_any"])
            factual_ok += int(ok)
            item["factual_ok"] = ok

        details.append(item)

    summary = {
        "n": len(rows),
        "recall_at_k_mean": round(sum(retrieval_scores) / len(retrieval_scores), 4)
        if retrieval_scores
        else None,
        "recall_at_10_mean": round(sum(recall10_scores) / len(recall10_scores), 4)
        if recall10_scores
        else None,
        "ndcg_at_10_mean": round(sum(ndcg10_scores) / len(ndcg10_scores), 4)
        if ndcg10_scores
        else None,
        "mrr_mean": round(sum(mrr_scores) / len(mrr_scores), 4) if mrr_scores else None,
        "intent_accuracy": round(intent_ok / intent_n, 4) if intent_n else None,
        "tool_accuracy": round(tool_ok / tool_n, 4) if tool_n else None,
        "factual_hit_rate": round(factual_ok / factual_n, 4) if factual_n else None,
        "latency_mean_s": round(sum(latencies) / len(latencies), 3) if latencies else None,
        "top_k": args.top_k,
    }
    payload = {"summary": summary, "details": details}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
